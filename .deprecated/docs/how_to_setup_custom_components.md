# 🧩 UGREEN NAS – Home Assistant Integration

This is a Home-Assistant integration for UGREEN NAS devices.
The integration is quite 'young' and development is active (so breaking changes might be necessary).

---

## ℹ️ Background & Limitations

- The UGreen API is currently undocumented to the public, so not all possibilities might be covered yet by the integration.
- UGREEN currently does **not provide a long-term access token**.
- This integration uses a **local Docker token server** running on your NAS.
- **All data stays entirely within your local network.**
- The integration is available though HACS now (listed as 'default' repository).
- The [Wiki](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/wiki/How-this-works) explains how everything is chained together.

---

## 🔧 Installation

## 🐳 Step 1: Add the integration to Home-Assistant

**Automatic:**

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tom-bom-badil&repository=home-assistant_ugreen-nas&category=Integration)

⚠️ **Note:** Installation may take up to 10-15 minutes.

1. Filter for the 'UGreen' integration in HACS (if you didn't use the button above).
2. Install the integration.
3. Restart Home-Assistant (only if asked to do so).

**Manual:**

1. Download the repository of the integration from [Github](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas).
2. Copy the folder `custom_components/ugreen` into your HA installation.
3. Restart Home-Assistant.

## 🐳 Step 2: Install the Docker UGREEN API Token Proxy on the NAS

To let Home Assistant receive a valid authentication token, you need to run a local token server on the NAS.

### Steps

1. Log in to your UGREEN NAS.

2. Install and open **Docker** (if not already installed).

3. Create a new project, e.g., `ugreen-access-token`.

4. Open the **Compose Editor** and paste the contents of this file:  
   [docker-compose.yaml](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/blob/main/addons/docker-compose.yaml)

5. Add your credentials under `environment` and adjust other settings if needed:

   ```yaml
   environment:
     UGREEN_NAS_API_SCHEME: "https"
     UGREEN_NAS_API_PORT: "9443"
     UGREEN_NAS_API_VERIFY_SSL: "false"
   ```

6. Click **Deploy** and start the container.

✅ If everything works correctly, you should see the following in the **Logs tab**:

```
Uvicorn running on http://0.0.0.0:4115 (Press CTRL+C to quit)
```

---

## 🔗 Set Up in Home Assistant

**Automatic:**

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ugreen)

**Manual:**

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.

2. Search for **UGREEN NAS** and confirm.

3. Configuration: Enter your connection details:  
   - API port (default: `9999`)
   - Token port (default: `4115`)
   - Username & password
   - Optional: Enable HTTPS and SSL certificate validation

4. Click **Submit** – done!

---

## 🧠 What Does This Integration Provide?

- **Sensors for:**
  - CPU & RAM (usage, frequency, model, temperature)
  - Upload/download speed
  - System and device information
  - Volumes, pools, and disks

- **Buttons for:**
  - Restart NAS
  - Shutdown NAS

---

## 🛠️ Troubleshooting

| Issue                      | Possible Solution                                                     |
|----------------------------|------------------------------------------------------------------------|
| `invalid_auth`             | Wrong username/password? Is the token server running?                 |
| `500 Internal Server Error`| Is two-factor authentication (2FA) enabled for this user?¹            |
| `cannot_connect`           | Is your NAS reachable from Home Assistant?                            |
| Token server not active    | Is the Docker container running correctly? Check the logs.            |
| Component not detected     | Restart Home Assistant and double-check your paths.                   |

¹ If you need 2FA for regular users, it’s recommended to create a dedicated admin user for this integration with a long, complex password.

---

## 🗣️ Feedback, Bugs & Ideas

Help us improve this integration!  
👉 [Open an issue on GitHub](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/issues)

---

## ❤️ Thank You & Have Fun!
