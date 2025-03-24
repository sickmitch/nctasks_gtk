# NCTasks

To use this: 1) clone the repo 2) run the entrypoint that is tasks.py 3) fill in setup. To update just pull the repo. <br />
**BE CAREFULL** it's very early in development so backup your calendars before using it, if you don't know [this](https://codeberg.org/BernieO/calcardbackup) can be very usefull.<br />
Do not use if the calendar MUST be preserved, I can't ensure on results.

## Dependencies
Tested only on Arch Linux for now, if you try on different platforms please report back.<br />
If you get errors on runtime and find out missing dependencies please PR to this README, much appreciate. <br />
`sudo pacman -S python-gobject gtk4 libadwaita python-requests python-icalendar python-dotenv` 

## Setup Help
  ### Create API key in Nextcloud from browser<br />
   - Login <br />
   - Personal Settings <br />
   - Security Tab -> scroll to bottom <br />
   - In the field at bottom of the page insert app name, not important is usefull only to later reference <br />
   - Copy the unique key shown in a dialog **it will be seen only now** <br />
   - Paste the key into NCTasks's setup dialog
  ### Find available calendars :<br />
    `curl -u $USER:$API_KEY -X PROPFIND "$BASE_URL/remote.php/dav/calendars/$USER/" | grep -oE "$USER/[^/]*/" | cut -c"$(wc -m<<<$USER)"- | tr -d '/' | awk 'length != 1'`


## To implement: <br />
 - [x] New Task <br />
 - [ ] Add secondary tasks
 - [x] Task management <br />
   - [x] Delete <br />
      - [x] Multiple selection
   - [x] Various fields managing <br />
      - [x] Remove due <br />
      - [x] Edit task <br />
      - [ ] Due hour manage 
 - [x] First use setup (WIP)<br />
 - [ ] Manage more then one calendar <br />
 - [ ] Graphical refinement<br />
   - [ ] Toggle for excluding completed tasks
   - [ ] Collapse secondary tasks
   - [ ] Add options button for setup dialog
   - [ ] Overall consistency
