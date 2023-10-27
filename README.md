This is a simple program for tracking time spent working more accurately by only tracking time spent in chosen programs and having a set idle timeout.

It is inspired by the AutoHothey script by Lemon Demon (Niel Cicierga) found [here](https://neilblr.com/post/58757345346). I was modifying that script to better suit my needs, but I ended up just remaking it with Python instead after the additions and motifications I wanted to make grew as I used it over time.

Things to keep in mind:
- It tracks the programs based on their executable path, so if you change where a program is in your file system, you'll need to use the Add Program button again. (This is done because some programs have the same exe name, using the window's handle doesn't track any child windows for the program, using the class name of the window's handle conflates all electron applications, and using the title wouldn't work because it can change for certain programs.)
- If you want to track only certain browsing, what I personally do is have Chrome and Chrome Beta open at once. I use Chrome for all non-work browsing, while setting the program to track Chrome Beta, which I only use for browsing that is to be considered "work". I use a different theme for each to make it easy to tell them apart, and it works well for me since I don't need to try to figure out all the individual sites that should be counted as work this way.
- This is a simple program by design because I don't want to overcomplicate my work tracking, but I do want to be confident my time was tracked accurately *enough*.
