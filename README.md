# Raspberry Pi Configuration

Configuration files and setup scripts for my Raspberry Pi setup.

## Setup
```bash
./scripts/setup.sh
```

## Backup
Backup volumes before major changes:
```bash
cp -r docker/volumes/* backups/$(date +%Y%m%d)/
```

