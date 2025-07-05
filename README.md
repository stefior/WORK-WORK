# WORK-WORK

A Windows-only productivity tool for accurately tracking time spent working in specific programs with idle detection and customizable alerts.

<div align="center">
  <img src="assets/timericon.ico" alt="Work Timer Icon" width="64" height="64">
</div>

## Background

This program is inspired by the AutoHotkey script by Lemon Demon (Neil Cicierega) found [here](https://web.archive.org/web/20160422221339/http://neilblr.com/post/58757345346). It originally started as modifications to that script, but grew into a complete Python rewrite to better suit evolving needs.
## Features

- **Automatic Time Tracking**: Only tracks time when you're actively working in designated programs
- **Idle Detection**: Pauses tracking when the system is idle beyond a configurable timeout
- **Visual Indicators**: Color-coded interface (cyan for active, red for inactive) with optional border alerts
- **Goal Setting**: Set daily work goals with notifications when reached
- **Customizable Shortcuts**: Configure global hotkeys for adding/removing programs
- **Audio Alerts**: Optional sound notifications for idle states
- **Time Management**: Save, restore, and manually adjust tracked time
- **Persistent Settings**: Remembers window position, tracked programs, and preferences

## Installation

An exe made using `pyinstaller` is in the Releases section, but Windows Defender thinks its malware, which seems to be a common issue. I tried signing it with a self-generated certificate, but to no avail.

If you'd like to build it from source, you can follow these steps:
1. Create a virtual environment: `python -m venv .venv`
2. Activate the virtual environment: `.\.venv\Scripts\activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the application: `pyinstaller main.spec`
5. The generated exe will be in the dist folder

## Usage

### Interface Overview

The application displays as a compact timer window that stays on top of other windows. The interface shows:
- **Time Display**: Current tracked time in HH:MM:SS format
- **MENU Button**: Access to all settings and options
- **Hide Checkbox**: Toggle to hide/show the time display
- **Color Coding**: Cyan background when actively tracking, red when inactive

### Default Global Hotkeys

- **Add program**: Win+Shift+=
- **Remove program**: Win+Shift+-

### Menu Options

- **Add/Remove Programs**: Manage which programs are tracked
- **Timeout Settings**: Configure idle timeout
- **Goal Time**: Set daily work goals with HH:MM:SS format
- **Hotkey Configuration**: Customize global shortcuts
- **Audio Settings**: Toggle idle indicator sound
- **Border Alerts**: Show screen borders when not working
- **Time Management**: Reset, resume, or manually adjust current time

## How It Works

### Program Tracking

The timer automatically detects when you're working in tracked programs by:
1. Polling the active window at a set interval
2. Checking if the current program is in your tracked list
3. Starting/stopping the timer based on program focus
4. Pausing when the system is idle beyond the configured timeout

## Important Notes

- **Program Detection**: Tracks programs by executable path, updating programs can require re-adding them sometimes
- **System Integration**: Alt+Tab, Win+Tab, desktop, and taskbar are considered part of File Explorer (explorer.exe), so it is set as tracked by default
- **Data Persistence**: Settings, window position, and previous time are automatically saved
