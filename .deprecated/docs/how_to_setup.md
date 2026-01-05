
# 🧪 UGreen NAS: Token Setup & Home Assistant Integration

> ✅ **Update (04/2025)**: Steps 1–3 can be skipped — you can now retrieve the token directly in your browser.

---

## 🔧 Preparations

<details>
  <summary>Click to expand</summary>
  <br/>

Before starting, make sure you have the following information ready:

- ✅ IP address of your NAS (e.g., `192.168.178.9`)
- ✅ Port number (usually `9999`)

> You can find this info in your browser’s address bar when accessing the NAS web interface:

<p align="center">
  <img src="https://github.com/user-attachments/assets/01f2415a-c07f-4730-8150-6131435e11f3" width="600"/>
</p>

</details>

---

## 🧼 Legacy Setup (Steps 1–3) — *Obsolete, for reference only*

> ⚠️ **Skip this section unless you're troubleshooting or using an older firmware.**

### ~~Step 1: Creating the token gathering script~~
<details>
  <summary>Click to expand</summary>
  <br/>

- In VS Code, create a `scripts/` folder.
- Add a new file: `get_ugreen_token.sh`
- Paste the contents from this repo’s version of that script.
- Run `chmod +x get_ugreen_token.sh` to make it executable.

<p align="center">
  <img src="https://github.com/user-attachments/assets/3c4808fb-0aa5-4188-bc4d-96c56c79f3a5" width="600"/>
</p>

</details>

### ~~Step 2: Retrieving the certificate number~~
<details>
  <summary>Click to expand</summary>
  <br/>

1. SSH into the NAS:  
   `ssh your_username@your_nas_ip`

2. Run:  
   `sudo ls /var/cache/ugreen-rsa`

3. Note the number from filenames like `1000.key` → that’s your certificate number.

<p align="center">
  <img src="https://github.com/user-attachments/assets/194275a3-57d7-4f7e-9bee-f43b96ee219c" width="600"/>
</p>

</details>

### ~~Step 3: Getting the REST token~~
<details>
  <summary>Click to expand</summary>
  <br/>

- Run the script: `./get_ugreen_token.sh`
- Enter IP, port, and the previously gathered certificate number.
- The script will output:
  1. Encrypted password
  2. Static token ✅ *(Use this one)*
  3. Session token

<p align="center">
  <img src="https://github.com/user-attachments/assets/e985f25f-0f16-4cfd-a552-08b50d444ef4" width="600"/>
</p>

</details>

---

## 🧠 Step 1: Get the Token (Easy Way)

<details open>
  <summary>Click to expand</summary>
  <br/>

- Open the NAS Web UI in your browser and log in.
- Press `F12` to open Developer Tools.
- Use `Ctrl + F` to search for `static_token` or `api_token`.

<p align="center">
  <img src="https://github.com/user-attachments/assets/19582953-1790-4a2e-9242-34fc56d32d43" width="600"/>
</p>

📌 **Important**:  
As of **firmware 1.3**, `static_token` no longer works. Use `api_token` instead.

Copy your token to a safe place — you’ll need it shortly.

</details>

---

## ⚙️ Step 2: Create Restart-Safe Home Assistant Entities

<details>
  <summary>Click to expand</summary>
  <br/>

1. Edit your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    homeassistant.components.rest: critical
    homeassistant.components.sensor: error

homeassistant:
  packages:
    ugreen_nas:
      # rest:           !include conf/ugreen_nas_rest.yaml
      # template:       !include conf/ugreen_nas_template_sensors.yaml
      input_text:       !include conf/ugreen_nas_input_text.yaml
```

2. Create a new folder: `conf/`  
3. Add the file: `ugreen_nas_input_text.yaml`  
4. Paste the contents from this repo  
5. Restart Home Assistant  
6. Go to **Developer Tools → States** and search for `ugreen`  
7. Set your local values and click “Set state”

<p align="center">
  <img src="https://github.com/user-attachments/assets/c324dfaa-f522-4017-87f2-e5520817c890" width="600"/>
</p>

</details>

---

## 🧩 Step 3: Define REST Sensors

<details>
  <summary>Click to expand</summary>
  <br/>

1. In `conf/`, create:

   - `ugreen_nas_rest.yaml`  
   - `ugreen_nas_template_sensors.yaml`

2. Paste the content from this repository into the respective files  
3. Edit `configuration.yaml` again and uncomment the `rest:` and `template:` lines  
4. Restart Home Assistant

<p align="center">
  <img src="https://github.com/user-attachments/assets/8714d257-00af-41c5-b28a-98b726e2028e" width="600"/>
</p>

5. After HA has restarted, run:  
   **Developer Tools → Actions → RESTful: Reload**

6. Check **Developer Tools → States**  
   → You should now see sensor data from your NAS.

🔗 [Known issues and limitations](https://github.com/Tom-Bom-badil/ugreen_nas/discussions/2)  
🔧 [Model-specific adjustments](https://github.com/Tom-Bom-badil/ugreen_nas/discussions/6)

</details>

---

## 🔁 Step 4: Adjust to Your System

<details>
  <summary>Click to expand</summary>
  <br/>

To fine-tune the setup to your system (disk count, fan sensors, etc.):

- Edit `conf/ugreen_nas_rest.yaml` → raw data sources  
- Edit `conf/ugreen_nas_template_sensors.yaml` → formatting, calculations, conversions  

You can reload these without restarting Home Assistant via:

- **Developer Tools → YAML → Reload Template Entities**
- **Developer Tools → YAML → Reload REST Entities**

🎉 Done! Your UGreen NAS is now integrated into Home Assistant.

> _Let me know if anything is unclear or doesn’t work for you — happy to improve the guide!_

</details>
