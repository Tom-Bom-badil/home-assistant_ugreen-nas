# UGreen NAS Monitoring

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%2341BDF5.svg)](https://www.home-assistant.io)
[![Custom integration](https://img.shields.io/badge/Custom%20Integration-%2341BDF5.svg)](https://www.home-assistant.io/getting-started/concepts-terminology)
[![HACS Listing](https://img.shields.io/badge/HACS%20Listing-default-green.svg)](https://github.com/hacs)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/graphs/commit-activity)
[![Version](https://img.shields.io/github/v/release/Tom-Bom-badil/home-assistant_ugreen-nas?sort=semver&color=green)](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/releases)
[![Stars](https://img.shields.io/github/stars/Tom-Bom-badil/home-assistant_ugreen-nas?style=flat&color=yellow)](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/stargazers)

---

## 🚀 Quick Overview

👉 This project enables **Home Assistant** to monitor data of a **UGOS based UGreen NAS** - *without modifying its operating system in any way*. No extra tools/scripts are installed in UGOS, no ssh access with cryptic shell commands is needed; no difficult container setup is required - we simply use what UGOS already provides.
<br/><br/>
<p align="center">
  <img width="80%" alt="system_view" src="https://github.com/user-attachments/assets/e40dfa67-93dc-44e4-a023-50e4203dc925" />
</p>
<br/>
The integration frequently retrieves and renews access authorization tokens, and queries data from the UGOS-builtin API (the same API that the UGOS Web GUI and the Mobile App are using).

---

## ⚙️ Setup Instructions

👉 [**Click here**](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/wiki/03-%E2%80%90-Installation) for the step-by-step installation guide on the project Wiki.
> ⏱️ Total setup time: *~5..10 minutes*

👉 [**Here**](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/wiki/Example-Dashboard-Page) you can find a step-by-step guide on how to get dashboard shown in the screenshot. After initial installation, you can [**fine tune**](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/wiki/Fine%E2%80%90tuning-your-dashboard) the dashboard to your individual NAS configuration and needs.
> 💬 Total dashboard installation time: *also ~5..10 minutes, plus the time for fine tuning*

---

## 📝 Notes & Feedback

👉 This integration was developed using a **UGreen DXP 4800+** and a **UGreen DXP 480T**. Other models and special setups (like GPU usage in the larger models) might not fully be covered. If you want to help us further developing the integration towards your specific setup, please contribute to the project by posting the API response of your NAS in the [Model Collection](https://github.com/Tom-Bom-badil/home-assistant_ugreen-nas/discussions/43).

**Contributions welcome!**

💬 [Start a discussion](https://github.com/Tom-Bom-badil/ugreen_nas/discussions) if you run into issues.  
✅ If it works for you, please let us know - it's great to hear success stories.  
📬 Pull requests and improvements are always appreciated!

---

*Thanks for using this integration and your feedback! 😊*
