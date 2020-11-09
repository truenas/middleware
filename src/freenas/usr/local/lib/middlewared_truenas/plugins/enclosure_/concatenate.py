from collections import defaultdict
import itertools
import operator
import re

from middlewared.service import Service, private

RE_DRAWER = re.compile(r"^(.+), Drawer #([0-9]+)$")


class EnclosureService(Service):
    @private
    async def concatenate_enclosures(self, enclosures):
        concatenated = defaultdict(list)
        result = []
        for enclosure in enclosures:
            if m := re.match(RE_DRAWER, enclosure["model"]):
                concatenated[m.group(1)].append((int(m.group(2)), enclosure))
            else:
                result.append(enclosure)

        for model, items in concatenated.items():
            items = [i[1] for i in sorted(items, key=operator.itemgetter(0))]

            id = "_".join(map(operator.itemgetter("id"), items))
            name = ", ".join(map(operator.itemgetter("name"), items))

            enclosure = items[0]
            items = items[1:]

            original_id = enclosure["id"]
            enclosure["id"] = id
            enclosure["name"] = name
            enclosure["model"] = model

            for elements in enclosure["elements"]:
                for element in elements["elements"]:
                    element["original"] = {
                        "enclosure": original_id,
                        "slot": element["slot"],
                    }

            for item in items:
                assert len(enclosure["elements"]) == len(item["elements"])

                for i, elements in enumerate(enclosure["elements"]):
                    item_elements = item["elements"][i]

                    assert elements["name"] == item_elements["name"]
                    assert elements["descriptor"] == item_elements["descriptor"]

                    for element in item_elements["elements"]:
                        elements["elements"].append(dict(
                            element,
                            original={
                                "enclosure_id": item["id"],
                                "slot": element["slot"],
                            },
                        ))

            slot = itertools.count(1)
            for elements in enclosure["elements"]:
                for element in elements["elements"]:
                    element["slot"] = next(slot)

            result.append(enclosure)

        return result
