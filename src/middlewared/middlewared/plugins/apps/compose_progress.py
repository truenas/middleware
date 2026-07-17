from __future__ import annotations

import json
import time
import typing

from middlewared.utils.size import format_size

ProgressCallback = typing.Callable[[float, str], None]

# Within a single layer pull, how much of the layer's work is attributed to
# downloading vs extracting it
LAYER_DOWNLOAD_WEIGHT = 0.75
# When resource (network/container/volume) events are expected ('up' actions),
# how much of the overall work is attributed to pulling images
PULL_PORTION_WITH_RESOURCES = 0.9


class ComposeProgressTracker:
    """
    Aggregate `docker compose --progress=json` events into a monotonically increasing
    overall fraction reported through `progress_callback(fraction, description)`.

    Compose emits one JSON object per stderr line. The events of interest are:
    - image pull layer events, carrying `parent_id` ('Image <tag>') and byte-level
      `current`/`total` for 'Downloading'/'Extracting' phases
    - image events (`id` = 'Image <tag>'), 'Pulled' marking an image done
    - resource events (Network/Container/Volume create/start), which follow pulls
      during 'up' actions

    Layer sizes are only announced as each layer starts downloading, so the byte
    denominator grows over time; reported progress is clamped to never decrease.
    """

    def __init__(
        self, progress_callback: ProgressCallback, resources_expected: bool, min_interval: float = 1.0,
    ):
        self.progress_callback = progress_callback
        self.resources_expected = resources_expected
        self.min_interval = min_interval
        # image id -> {'done': bool, 'layers': {layer id -> layer state}}
        self.images: dict[str, dict[str, typing.Any]] = {}
        # resource id (e.g. 'Container myapp-web-1') -> done
        self.resources: dict[str, bool] = {}
        self._max_fraction = 0.0
        self._last_emitted: tuple[float, str] | None = None
        self._last_emit_at = float('-inf')
        self._resource_description = ''

    def feed_line(self, line: str) -> None:
        line = line.strip()
        if not line.startswith('{'):
            return

        try:
            event = json.loads(line)
        except ValueError:
            return

        if not isinstance(event, dict) or event.get('error'):
            return

        ident = event.get('id')
        if not isinstance(ident, str) or event.get('status') not in ('Working', 'Done'):
            return

        if parent_id := event.get('parent_id'):
            self._feed_layer(parent_id, ident, event)
        elif ident.startswith('Image '):
            self._feed_image(ident, event)
        else:
            self._feed_resource(ident, event)

        self._emit()

    def flush(self) -> None:
        """Emit the current state, bypassing throttling. Call after the event stream ends so the
        final events, which usually land within the throttle interval of the previous emission,
        are not lost."""
        self._emit(force=True)

    def _feed_layer(self, image_id: str, layer_id: str, event: dict[str, typing.Any]) -> None:
        image = self.images.setdefault(image_id, {'done': False, 'layers': {}})
        layer = image['layers'].setdefault(layer_id, {'total': 0, 'download': 0.0, 'extract': 0.0, 'done': False})
        text, phase_fraction = event.get('text'), None
        current, total = event.get('current'), event.get('total')
        if isinstance(current, (int, float)) and isinstance(total, (int, float)) and total > 0:
            layer['total'] = total
            phase_fraction = min(current / total, 1.0)

        if text == 'Downloading':
            if phase_fraction is not None:
                layer['download'] = phase_fraction
        elif text == 'Extracting':
            layer['download'] = 1.0
            if phase_fraction is not None:
                layer['extract'] = phase_fraction
        elif text == 'Download complete':
            layer['download'] = 1.0
        elif text in ('Pull complete', 'Already exists'):
            layer['done'] = True

    def _feed_image(self, image_id: str, event: dict[str, typing.Any]) -> None:
        image = self.images.setdefault(image_id, {'done': False, 'layers': {}})
        if event.get('status') == 'Done':
            image['done'] = True

    def _feed_resource(self, resource_id: str, event: dict[str, typing.Any]) -> None:
        done = event.get('status') == 'Done'
        self.resources[resource_id] = self.resources.get(resource_id) or done
        if done:
            self._resource_description = f'{event.get("text")} {resource_id}'

    @staticmethod
    def _layer_fraction(layer: dict[str, typing.Any]) -> float:
        if layer['done']:
            return 1.0
        return LAYER_DOWNLOAD_WEIGHT * layer['download'] + (1 - LAYER_DOWNLOAD_WEIGHT) * layer['extract']

    def _image_fraction(self, image: dict[str, typing.Any]) -> float:
        if image['done']:
            return 1.0

        layers = image['layers'].values()
        known_sizes = [layer['total'] for layer in layers if layer['total'] > 0]
        if not known_sizes:
            return 0.0

        # Layer sizes are announced lazily as each layer starts downloading. Weighing layers of
        # still-unknown size as if they were average-sized keeps an early small completed layer
        # from inflating the overall fraction.
        default_weight = sum(known_sizes) / len(known_sizes)
        denominator = sum(layer['total'] or default_weight for layer in layers)
        return sum(
            (layer['total'] or default_weight) * self._layer_fraction(layer) for layer in layers
        ) / denominator

    def _pull_fraction(self) -> float:
        if not self.images:
            return 0.0
        return sum(map(self._image_fraction, self.images.values())) / len(self.images)

    def _compute(self) -> tuple[float, str]:
        pull_fraction = self._pull_fraction()
        if self.resources_expected:
            resources_fraction = sum(self.resources.values()) / len(self.resources) if self.resources else 0.0
            if self.images:
                fraction = (
                    PULL_PORTION_WITH_RESOURCES * pull_fraction
                    + (1 - PULL_PORTION_WITH_RESOURCES) * resources_fraction
                )
            else:
                # All images were already present, no pull happened - resource
                # (network/container) events are the whole operation
                fraction = resources_fraction
        else:
            fraction = pull_fraction

        if self.images and not all(image['done'] for image in self.images.values()):
            description = 'Pulling app images'
            layers = [
                layer for image in self.images.values() for layer in image['layers'].values() if layer['total'] > 0
            ]
            if total_bytes := sum(layer['total'] for layer in layers):
                downloaded_bytes = sum(layer['total'] * layer['download'] for layer in layers)
                description += f' ({format_size(int(downloaded_bytes))} / {format_size(int(total_bytes))})'
        elif self._resource_description:
            description = self._resource_description
        else:
            description = 'Deploying app resources' if self.resources_expected else 'Pulling app images'

        return fraction, description

    def _emit(self, force: bool = False) -> None:
        fraction, description = self._compute()
        fraction = self._max_fraction = max(fraction, self._max_fraction)
        now = time.monotonic()
        if self._last_emitted == (fraction, description) or (
            not force and now - self._last_emit_at < self.min_interval
        ):
            return

        self._last_emitted = (fraction, description)
        self._last_emit_at = now
        self.progress_callback(fraction, description)
