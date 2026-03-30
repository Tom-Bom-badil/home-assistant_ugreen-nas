# UGreen NAS Monitoring

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%2341BDF5.svg)](https://www.home-assistant.io)
[![Custom integration](https://img.shields.io/badge/Custom%20Integration-%2341BDF5.svg)](https://www.home-assistant.io/getting-started/concepts-terminology)
[![HACS Listing](https://img.shields.io/badge/HACS%20Listing-default-green.svg)](https://github.com/hacs)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/graphs/commit-activity)
[![HA Analytics](https://img.shields.io/badge/dynamic/json?url=https://analytics.home-assistant.io/custom_integrations.json&query=$.ugreen.total&label=HA%20Analytics%20%2A&suffix=%20active%20installations&color=green)](https://analytics.home-assistant.io/)

---

## 🚀 Quick Overview

👉 This project enables **Home Assistant** to monitor settings and operational data of a **UGOS-based UGreen NAS** - *without modifying its operating system in any way*. No extra tools/scripts are installed in UGOS, no ssh access with cryptic shell commands is needed, no difficult container setup is required - we simply use what UGOS already provides.
<br/><br/>
<p align="center">
  <img width=80% alt="img1" src="https://github.com/user-attachments/assets/e40dfa67-93dc-44e4-a023-50e4203dc925" />
</p>
<br/>
The integration automatically retrieves and renews access authorization tokens as needed, and queries data from the UGOS-builtin API by using those tokens (the same API that the UGOS Web GUI and the UGOS Apps are using).

---

## ⚙️ Setup Instructions

👉 [**Click here**](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/wiki/04-%E2%80%90-Installation-of-the-integration) for the step-by-step installation guide on the project Wiki. In case of problems showing up during installation, we have prepared a [**troubleshooting guide**](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/discussions/176) for you on the discussions.
> ⏱️ Total setup time: *~5..10 minutes*

👉 [**Here**](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/wiki/05-%E2%80%90-The-premade-dashboard-page) you can find a step-by-step guide on how to get a dashboard as shown in the screenshot. After initial installation, there is another document on the Wiki explaining how to fine-tune the premade dashboard, or how to even make your own one.
> ⏱️ Total dashboard installation time: *also ~5..10 minutes, plus some time for fine tuning*

---

## 📝 Notes & Feedback

👉 This integration was developed using a **UGreen DXP 4800+** and a **UGreen DXP 480T**. Other models and highly advanced configurations (like GPU usage in the larger models) might not fully be covered yet. If you want to help us further developing the integration towards your specific setup, please contribute to the project by posting the API response of your NAS in the [Model Collection](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/discussions/43).

**Contributions welcome!**

💬 [Start a discussion](https://github.com/Tom-Bom-badil/ugreen_nas/discussions) if you run into issues.  
✅ If it works for you, please let us know - it's great to hear success stories.  
📬 Pull requests and improvements are always appreciated!

*Thanks for using this integration, and for your feedback! 😊*


---

<sub>* Active installations: Analytics numbers are based on HA Analytics opt-in users, estimated to represent less than ¼ of all active HA installations. Click the button for more info.</sub>