# Testing the Backup-Drive Auto-Recovery

This document explains how to deliberately reproduce each backup-drive failure
mode that Nodealyzer's auto-recovery handles, so you can verify the behavior
end-to-end. Run the **inject** commands on the **Receiver** (the machine holding
the backup drive), then trigger a normal Nodealyzer run on the **Server** and
read the email report.

> ⚠️ **WARNING — these commands deliberately break the backup drive.**
> They unmount it, force it read-only, and (in one test) **intentionally corrupt
> ext4 metadata on the live backup partition**. Only run them against the
> **Receiver's backup drive**, never on a system/root partition. The backup
> contents are expendable (Nodealyzer re-pushes them on the next run), but a
> wrong device name here is destructive — **double-check the device and mount
> point first**. Each test below lists how to undo it.

## Find the device and mount point

The recovery logic resolves these from `/etc/fstab` based on the configured
`backup_server_remote_directory`. Look them up the same way before testing:

```sh
# On the Receiver — substitute your configured backup_server_remote_directory:
findmnt --fstab -n -o SOURCE,TARGET --target <backup_server_remote_directory>
```

Below, `<MOUNT_POINT>` is the TARGET and `<DEVICE>` is the SOURCE (e.g.
`/dev/sda1`) from that command.

## Prerequisites

* The backup drive is an `/etc/fstab`-managed mount on the Receiver (with
  `nofail`), per the README.
* Passwordless sudo for `umount`/`mount`/`e2fsck` is configured on the Receiver
  (per the README) — except where a test specifically removes it.
* Run Nodealyzer on the Server the normal way, e.g.
  `/home/USER/Nodealyzer/Nodealyzer.py`.

---

## Test 1 — Read-only filesystem (safest, fully reversible)

Exercises the full detect → umount → e2fsck → remount → retry orchestration
without corrupting anything.

**Inject (Receiver):**
```sh
sudo mount -o remount,ro <MOUNT_POINT>
```

**Run:** trigger Nodealyzer on the Server.

**Expect:** rsync fails with `Read-only file system`; auto-recovery runs
`umount → e2fsck -D -f -y → mount` (e2fsck will likely report the volume clean —
that's fine, it still validates the flow); the retry succeeds. Email shows
**Remote Data Backup = Pass\*** and **Backup Drive Repair = Repaired**.

**Undo:** nothing — the repair remounts the drive read-write.

---

## Test 2 — Drive not mounted, auto-remount

**Inject (Receiver):**
```sh
sudo umount <MOUNT_POINT>
```

**Run:** trigger Nodealyzer on the Server.

**Expect:** the pre-flight check finds the drive unmounted, remounts it via
fstab, and the backup proceeds normally. Email shows **Backup Drive Mounted =
Remounted**.

**Undo:** nothing — the pre-flight remounts it.

---

## Test 3 — Not mounted + cannot remount (the write-guard)

Verifies that when the drive is unmounted **and** can't be remounted, Nodealyzer
**skips the sync entirely** rather than writing into the bare mount-point
directory on the Receiver's root filesystem (which would silently fill it).

**Inject (Receiver):**
```sh
# Temporarily remove the recovery sudo permission AND unmount the drive:
sudo mv /etc/sudoers.d/nodealyzer-recovery /etc/sudoers.d/nodealyzer-recovery.bak
sudo umount <MOUNT_POINT>
```

**Run:** trigger Nodealyzer on the Server.

**Expect:** the pre-flight cannot remount, so **rsync is skipped**. Email shows
**Backup Drive Mounted = Fail** and **Remote Data Backup = Fail (SKIPPED)** with
the prominent "backup drive was NOT mounted … skipping to avoid writing to root"
warning.

**Verify nothing was written to root** (the mount point should be an empty
directory, and root usage unchanged):
```sh
ls -la <MOUNT_POINT>          # should be empty / unchanged
df -h /                       # root filesystem usage should not have jumped
```

**Undo (Receiver):**
```sh
sudo mv /etc/sudoers.d/nodealyzer-recovery.bak /etc/sudoers.d/nodealyzer-recovery
sudo mount <MOUNT_POINT>
```

---

## Test 4 — Real ext4 metadata corruption (the original failure)

Reproduces the actual `Bad message (74)` / directory-checksum corruption on the
**live backup partition**, so you can confirm `e2fsck -D` genuinely repairs it.
This is real corruption — re-read the warning at the top of this file.

**Inject (Receiver):**
```sh
# 1) Unmount the backup drive.
sudo umount <MOUNT_POINT>

# 2) Confirm the filesystem block size (usually 4096).
sudo dumpe2fs -h <DEVICE> | grep -i 'Block size'

# 3) Pick a directory that exists ON the backup filesystem and find one of its
#    data blocks. Paths in debugfs are relative to the filesystem root (i.e. to
#    <MOUNT_POINT>). Replace /some/backed-up/dir accordingly:
sudo debugfs -R "stat /some/backed-up/dir" <DEVICE>
#    In the output, note a block number under "BLOCKS:" e.g. "(0):123456".

# 4) Overwrite that one directory block with garbage (do NOT update its
#    checksum). Use bs = block size from step 2, seek = the block number:
sudo dd if=/dev/urandom of=<DEVICE> bs=4096 count=1 seek=123456 conv=notrunc

# 5) Remount so the next sync hits the corrupted directory block.
sudo mount <MOUNT_POINT>
```

With `metadata_csum` enabled (the default on modern mkfs.ext4), the kernel
rejects the corrupted directory block on read with a checksum error, which rsync
surfaces as `Bad message (74)`.

**Run:** trigger Nodealyzer on the Server.

**Expect:** rsync fails with `Bad message (74)`; auto-recovery detects it,
resolves `<DEVICE>` from fstab, runs `umount → e2fsck -D -f -y → mount`
(e2fsck **actually repairs** this time), and the retry succeeds. Email shows
**Remote Data Backup = Pass\*** and **Backup Drive Repair = Repaired**, including
the e2fsck output in the body.

**Undo:** the auto-recovery itself repairs the filesystem. If you need to fix it
manually (e.g. you disabled `autofix_filesystem`):
```sh
sudo umount <MOUNT_POINT>
sudo e2fsck -D -f -y <DEVICE>
sudo mount <MOUNT_POINT>
```
e2fsck may relink any entries from the clobbered directory into `lost+found`;
that's expected, and the next Nodealyzer run re-pushes the affected files.

---

## Test 5 — Permission denied (no passwordless sudo)

**Inject (Receiver):**
```sh
sudo mv /etc/sudoers.d/nodealyzer-recovery /etc/sudoers.d/nodealyzer-recovery.bak
```
Then reproduce Test 1's read-only condition:
```sh
sudo mount -o remount,ro <MOUNT_POINT>
```

**Run:** trigger Nodealyzer on the Server.

**Expect:** auto-recovery cannot escalate; email clearly states *"We tried to
auto-recover the remote backup drive, but don't have permission to do so. Follow
the README instructions…"*, and the rest of the run still completes (Backup
Drive Repair = Fail).

**Undo (Receiver):**
```sh
sudo mount -o remount,rw <MOUNT_POINT>   # or: sudo umount <MOUNT_POINT>; sudo mount <MOUNT_POINT>
sudo mv /etc/sudoers.d/nodealyzer-recovery.bak /etc/sudoers.d/nodealyzer-recovery
```

---

## Test 6 — Guardrails (no injection needed)

These confirm the auto-recovery does **not** act when it shouldn't:

* A plain rsync warning (e.g. a file that vanished mid-sync, rsync exit code 23)
  with **no** `Bad message (74)` or `Read-only file system` in the output must
  **not** trigger an fsck — the report shows **Backup Drive Repair = N/A**.
* A failure containing `Input/output error` (suspected failing hardware) or
  `No space left on device` (full disk) must **not** trigger an fsck — the
  report flags it for manual attention (skipped, unsafe to auto-repair).

These are best verified by code review of `repairRemoteBackupDrive()` plus
observing a normal successful run (which reports **Backup Drive Repair = N/A**).
