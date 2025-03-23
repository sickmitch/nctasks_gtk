# NCTasks
Visualization works fine. Ordering takes into account **parent-son relation, due and priority** in this order.<br />

## Setup Help
  ### Create API key in Nextcloud from browser<br />
   - Login <br />
   - Personal Settings <br />
   - Security Tab -> scroll to bottom <br />
   - In the field at bottom of the page insert app name, not important is usefull only to later reference <br />
   - Copy the unique key shown in a dialog, **will be seen only now** <br />
   - Paste the key into NCTasks's setup dialog
  ### Find available calendars :<br />
    `curl -u $USER:$API_KEY -X PROPFIND "$BASE_URL/remote.php/dav/calendars/$USER/" | grep -oE "$USER/[^/]*/" | cut -c"$(wc -m<<<$USER)"- | tr -d '/' | awk 'length != 1'`


To implement: <br />
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
   - [ ] Overall consistency
