# Recover external storage

The supervisor requires the registered external volume UUID, external-device status, exact mountpoint and writable volume. It also checks the marker, stable media link, writable media directories and their containment on that volume. A folder left behind at the mountpoint cannot satisfy the gate.

Filesystem checks run in a disposable child with an eight-second deadline. If I/O stalls, the child is killed and reaped when possible; another probe is suppressed while a previous child remains stuck. A timeout or blocked probe leaves storage unavailable rather than allowing the services to use an unverified path.

Start with the installed controller and its private registered storage profile. Check the physical connection and correct volume, then use the storage and status checks in [operations](operations.md). Restore the intended volume and its paths; do not replace the marker or register another disk merely to bypass a failure. If a probe remains blocked, investigate the underlying filesystem or connection before retrying. Completion requires a new successful full storage verification and advancing service status; a responding proxy alone is insufficient.
