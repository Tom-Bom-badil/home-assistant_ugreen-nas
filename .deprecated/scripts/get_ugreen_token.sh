#!/bin/bash

# Enter the configuration to extract the token
read -p "NAS IP (e.g. 192.168.178.234): " NAS_IP
read -p "NAS Port (e.g. 9999): " NAS_PORT
read -p "NAS User (e.g. tom): " NAS_USER
read -s -p "NAS User Password (to be re-entered below): " PASSWORD
echo
read -p "NAS Certificate Number (e.g. 1000): " USER_ID
echo "Please ignore any 'Could not chdir to ...' (if even shown)"

# Path to public key
KEY_PATH="/var/cache/ugreen-rsa/${USER_ID}.pub"

# Prepare remote commands
REMOTE_COMMAND="echo '$PASSWORD' | sudo -S bash -c 'echo -n \"$PASSWORD\" | sudo openssl pkeyutl -encrypt -inkey $KEY_PATH -pubin | base64'"

# run ssh on UGOS
RAW_OUTPUT=$(ssh -o StrictHostKeyChecking=no ${NAS_USER}@${NAS_IP} "$REMOTE_COMMAND")

# Remove line breaks from output
RAW_OUTPUT_SINGLE_LINE=$(echo "$RAW_OUTPUT" | tr -d '\n')

# Extract encrypted password
ENCRYPTED_PASSWORD=$(echo "$RAW_OUTPUT_SINGLE_LINE" | grep -o '[A-Za-z0-9+/=]\+==$')

# Check / output encrypted password
if [[ -n "$ENCRYPTED_PASSWORD" ]]; then
    echo -e "\n\nEncrypted password: $ENCRYPTED_PASSWORD"
else
    echo -e "\n\nEncrypted password not found, exiting."
    exit 1
fi

# Generate tokens through API
TOKEN_RESPONSE=$(curl -s -X POST "http://${NAS_IP}:${NAS_PORT}/ugreen/v1/verify/login" \
    -H "Content-Type: application/json" \
    -d "{
        \"username\": \"${NAS_USER}\",
        \"password\": \"${ENCRYPTED_PASSWORD}\",
        \"keepalive\": true
    }")

# Extract tokens from API
STATIC_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"static_token":"[^"]*"' | sed 's/"static_token":"//;s/"//')
SESSION_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"token":"[^"]*"' | sed 's/"token":"//;s/"//')

# Check / output tokens
if [[ -n "$STATIC_TOKEN" && -n "$SESSION_TOKEN" ]]; then
    echo "Static Token: $STATIC_TOKEN"
    echo -e "Session Token: $SESSION_TOKEN\n"
else
    echo "Could not extract token, exiting."
    exit 1
fi
