## Cloud Tests

Tests that perform cloud backups or access remote repositories.

When two integration tests run at the very same time and share an external resource (e.g. an S3 bucket for backups), they will conflict, resulting if false negatives. Tests in this directory are executed under a lock so that they cannot be run by multiple testing instances simultaneously, avoiding such failures.