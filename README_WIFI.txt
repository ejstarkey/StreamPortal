==========================
Wi-Fi Mode Toggle Instructions
==========================

This system uses the wlp9s0 Wi-Fi interface in one of two modes:

1. Access Point (AP) Mode
   - Broadcasts SSID: cornerpins
   - WPA2 password: I.@m.b@tm@n.83
   - Used to provide wireless access to clients

2. Client (STA) Mode
   - Connects to an upstream Wi-Fi network
   - Requires SSID and password set in: /etc/wpa_supplicant/wpa_supplicant-wlp9s0.conf

-------------------------
HOW TO TOGGLE MODES
-------------------------

To switch to Access Point (AP) mode:
    sudo /home/cornerpins/portal/wifi_toggle.sh ap

To switch to Wi-Fi Client (STA) mode:
    sudo /home/cornerpins/portal/wifi_toggle.sh sta

-------------------------
Edit Wi-Fi Client Details
-------------------------

To change the upstream SSID or password:

    sudo nano /etc/wpa_supplicant/wpa_supplicant-wlp9s0.conf

Then run:
    sudo /home/cornerpins/portal/wifi_toggle.sh sta

-------------------------
Verify Status
-------------------------

Check AP status:
    sudo systemctl status hostapd

Check STA connection:
    sudo systemctl status wpa_supplicant@wlp9s0

-------------------------
NOTES
-------------------------
