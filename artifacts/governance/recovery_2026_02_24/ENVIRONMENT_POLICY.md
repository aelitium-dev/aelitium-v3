# ENVIRONMENT POLICY — AELITIUM

## 1. Code Location
All active development MUST occur inside:
~/ (Linux filesystem)

Never develop primary code in:
 /mnt/c

## 2. Git Policy
- Each phase must be versioned.
- No development without Git initialized.

## 3. Backup Policy
- Weekly snapshot commit.
- Monthly external backup.

## 4. WSL Safety Rule
Before changing Windows profile:
- Export distro using:
  wsl --export Ubuntu backup.tar
