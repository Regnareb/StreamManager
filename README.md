# Twitch Autoswitcher

**Switch automatically the game on Twitch when you are streaming**

- It stop all services that impede the upload (Dropbox, Backblaze, Duplicati) or the stream (Synergy), launch OBS and begin the stream immediately and automatically.
- Every 60 seconds it checks the foreground windows and change the game on Twitch if it changed.
- When OBS is closed, all the services are restarted.
