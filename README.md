# Introduction

This is a Windows program for tracking time spent working more accurately by only tracking time spent in chosen programs and having a set idle timeout.

The program by simple by design because I don't want to overcomplicate my work tracking, but I do want to be confident my time was tracked accurately *enough*.

It is inspired by the AutoHothey script by Lemon Demon (Niel Cicierga) found [here](https://web.archive.org/web/20160422221339/http://neilblr.com/post/58757345346). I was modifying that script to better suit my needs, but I ended up just remaking it with Python instead after the additions and modifications I wanted to make grew as I used it over time.

## Installation

An exe made using `pyinstaller` is in the Releases section, but Windows Defender thinks its malware, which seems to be a common issue. I tried signing it with a self-generated certificate, but to no avail.

If you'd like to build the exe from source, you can install the dependencies with `pip install keyboard psutil simpleaudio pyqt5 pyqt5-tools pypiwin32`, then run `pyinstaller main.spec`. The exe will be in the project's `./dist` directory.

## Default global hotkeys

- **A**dd program: Ctrl+Win+Alt+A
- **R**emove program: Ctrl+Win+Alt+R

## Things to keep in mind

- If you try to add a program that was already added or remove a program that isn't in the list, the screen will say "already+" instead of "added" or "already-" instead of "removed".
- It tracks the programs based on their executable path, so if you change where a program is in your file system, you'll need to use the Add Program button again. You may also need to re-add the program if updating it changes its path. (This is done because some programs have the same exe name, using the window's handle doesn't track any child windows for the program, using the class name of the window's handle conflates all electron applications, and using the title wouldn't work because it can change for certain programs.)
- The Alt+Tab switcher, the Win+Tab switcher, the desktop, and the task bar are all considered as part of the file explorer. So, if it goes red for a second while doing something like Alt+Tabbing, it's simply because you don't have the file explorer (explorer.exe) as a tracked program.
- If you'd like to still have it on your screen without covering up any programs (e.g. covering part of the last line in your terminal), what I did is increase the height of the taskbar on my secondary monitor and put the program at the bottom right of the screen.
