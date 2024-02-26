This is a simple program for tracking time spent working more accurately by only tracking time spent in chosen programs and having a set idle timeout.

This is a simple program by design because I don't want to overcomplicate my work tracking, but I do want to be confident my time was tracked accurately *enough*.

It is inspired by the AutoHothey script by Lemon Demon (Niel Cicierga) found [here](https://web.archive.org/web/20160422221339/http://neilblr.com/post/58757345346). I was modifying that script to better suit my needs, but I ended up just remaking it with Python instead after the additions and motifications I wanted to make grew as I used it over time.

# Default global hotkeys
- **A**dd program: Ctrl+Win+Alt+A
- **R**emove program: Ctrl+Win+Alt+R

# Things to keep in mind
- If you try to add a program that was already added or remove a program that isn't in the list, the screen will say "already+" instead of "added" or "already-" instead of "removed".
- It tracks the programs based on their executable path, so if you change where a program is in your file system, you'll need to use the Add Program button again. (This is done because some programs have the same exe name, using the window's handle doesn't track any child windows for the program, using the class name of the window's handle conflates all electron applications, and using the title wouldn't work because it can change for certain programs.)
- The Alt+Tab switcher, the Win+Tab switcher, the desktop, and the task bar are all considered as part of the file explorer. So, if it goes red for a second while doing something like Alt+Tabbing, it's simply because you don't have the file explorer (explorer.exe) as a tracked program.
- If you'd like to still have it on your screen without covering up any programs (e.g. covering part of the last line in your terminal), what I did is increase the height of the taskbar on my secondary monitor and put the program at the bottom right of the screen.
