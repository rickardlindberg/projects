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
USER_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCf2CDrDvB5WV+EK4flL/j6qkO00ZGrjcldmgzt2326F9M2kfuH5Hd37lmOQwf5B21y1Tm2n+O4GF0jAE0AiHxZdx4zAB8MUzHiZCfdu309SWkkaEy3016lUedfHttvQkiA66kDw6t1Rp0SPWsOtw2ErYkF9fVIwHvEgPtXP8iIdRdlmx5W1whSkyN3Be91M8et8xaq8Ot3gsC8jCtLlACGjkrFYFmcvAASy63JQcfg+E7136cU8QrHXoQrln1Q4qLTDYQEwyCIIpi0ZbLThorTMZfgx9XNosZYSkpRUqjC8s1C20hw+5CAwmJicqFctEH2aOcDrW+tiM77AgfxMZ426teWZIm/Fd/Bc4Vnt/qxhXi9s1RLUMEsVrwo2T818Q0j0hSVLkUEjSC/FcqZXaZnHMTDxj3M+kLUblv9WOWDWnuf2G2BHQBVVtXuEiyL3HgZX/2trKfYFkJm2XREVgVHc4p6rWshdziTFbC6O2yrxuRkszsvae3htGclWA8lPT70KOEuAg3/gOLPMnD/4qoykLJvqEpI609WPO7VezA/N+rddZ5LJ4EnnxozfeHdL5lbiuB8xj3IiWhNMGiDcuSx+HDFs8Y1EglYfR7kYW0kr0Gv+y3PSl4bMnVhue43NeP/PKAa/3WUS5iA1cdRA/yLz6o7qbxrbQbS0FlFHYQr3w== ricli85@gmail.com"
INSTANCE_NAME=projects
DOMAIN=projects.rickardlinberg.me

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

# Set hostname

hostnamectl set-hostname $DOMAIN
systemctl restart postfix

# Done

echo "Setup OK!"
echo
echo "Try ssh $USER@<linode ip>"
