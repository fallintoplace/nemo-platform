---
description: Start local NeMo Platform services or run a task module
---
Start local NeMo Platform services with optional service/controller selection, or run a task module

## Workflow

Determine the command based on options, each line being one example on how to run things

```bash
  export DATABASE_DIALECT=sqlite
  export DATABASE_PATH=$HOME/.local/share/nemo/nmp-platform.db
  export UVICORN_RELOAD=true
  # Default
  uv run nemo services run
  # Specific config
  uv run nemo services run --config packages/nmp_platform/config/local.yaml
  # One service
  uv run nemo services run --services hello-world
  # Jobs controller
  uv run nemo services run --controllers jobs
  # Jobs service and controller
  uv run nemo services run --services jobs --controllers jobs
  # Task execution
  uv run nemo-platform run task --task nmp.hello_world.tasks.hello_world
  uv run nemo-platform run task --task nmp.hello_world.tasks.hello_world --config '{"key": "value"}'
```
