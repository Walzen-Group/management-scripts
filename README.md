# This is a collection of management scripts

## portainer-stack-manager

Usage:


Single stack:
```bash
py manager.py --start   --stack-name    <stack-name>
              --stop
              --restart
```

Multiple stacks:
```bash
py manager.py --start   --all
              --stop
              --restart
```

If the restart option is picked, only stacks that are running will be restarted.

**BEWARE**: Using start will start all stacks, even those that are not supposed to run because they have been disabled before. So use that with care.

