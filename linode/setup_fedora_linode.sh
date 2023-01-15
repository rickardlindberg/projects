#!/usr/bin/env bash

# To set up a Linode initially:
#
#     cat ./setup_fedora_linode.sh | ssh root@<linode ip> bash -
#
# After the setup, this should work:
#
#     ssh $USER@<linode ip>

set -e

USER=projects
USER_PUBLIC_KEY=$(cat ~/.ssh/id_rsa.pub)
INSTANCE_NAME=projects

# Add user

if ! id $USER; then
    useradd $USER
fi

# Setup SSH key

mkdir -p /home/$USER/.ssh
echo $USER_PUBLIC_KEY > /home/$USER/.ssh/authorized_keys
chown -R $USER:$USER /home/$USER/.ssh
chmod 600 /home/$USER/.ssh/authorized_keys

# Secure SSH

SSHD_CONFIG=/etc/ssh/sshd_config
generate_sshd_config() {
    cat $SSHD_CONFIG | grep -v '^PrintLastLog' | grep -v '^PermitRootLogin' | grep -v '^PasswordAuthentication'
    echo "PrintLastLog no"
    echo "PermitRootLogin no"
    echo "PasswordAuthentication no"
}
generate_sshd_config > $SSHD_CONFIG.new
mv $SSHD_CONFIG.new $SSHD_CONFIG
chmod 600 $SSHD_CONFIG
systemctl restart sshd.service

# Add project folder

mkdir -p /opt/$INSTANCE_NAME
chown $USER:$USER /opt/$INSTANCE_NAME

# Install dependencies

dnf install -y git python3 postfix
systemctl enable postfix
systemctl start postfix

# Done

echo "Setup OK!"
echo
echo "Try ssh $USER@<linode ip>"
