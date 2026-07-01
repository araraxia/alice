#/usr/bin/bash

# Update vars before running
FSTAB="/etc/fstab"
BACKUP="/etc/fstab.$(date +%F-%H%M%S).bak"
FS_MNT="/mnt/none"
FS_NWP="//0.0.0.0"
MOUNT_DIRS=(
	""
	""
	""
	""
	""
)

USERNAME=""
PASSWORD=""
UID=""
GID=""
MNT_CMD_TAIL="cifs defaults,username=${USERNAME},password=${PASSWORD},uid=${UID},gid=${GID},noserverino,vers=3.02 0 0"

# Backup fstab
echo "Making backup of /etc/fstab"
cp "$FSTAB" "$BACKUP"

# Iterate through each mount
echo "Iterating through mounts"
for dir in "${MOUNT_DIRS[@]}"; do
	FULL_MNT_PATH="${FS_MNT}/${dir}"
	NETWORK_PATH="${FS_NWP}/${dir}"
	MOUNT="${NETWORK_PATH} ${FULL_MNT_PATH} ${MNT_CMD_TAIL}"
	echo "Full mount path: $FULL_MNT_PATH"

	# Create mount dir if needed
	if [ ! -d "$FULL_MNT_PATH" ]; then
		mkdir -p "$FULL_MNT_PATH"
		echo "Created $FULL_MNT_PATH"
	fi

	# Check if entry already exists in /etc/fstab
	if grep -qE "^[^#]*[[:space:]]+$FULL_MNT_PATH[[:space:]]" "$FSTAB"; then
		echo "Entry for ${FULL_MNT_PATH} already exists, skipping."
		continue
	fi

	# Add entry to /etc/fstab
	echo "Appending entry to fstab"
	echo "$MOUNT" | sudo tee -a "$FSTAB" > /dev/null
	echo "Added entry: $MOUNT"
done
echo "End of script."
