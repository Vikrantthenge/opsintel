# Account and project access setup

OpsIntel 2.5 adds local accounts to the existing application. No default username or password is included.

## First startup or upgrade from 2.4 and earlier

1. Stop the old app. Keep a backup of its entire `data` folder.
2. Extract the new app and place that existing `data` folder beside the new `app.py`. Do not leave the old, unprotected app running.
3. Open a terminal in the new app folder and run:

       python -m pip install -r requirements.txt
       python -m streamlit run app.py

4. OpsIntel shows Set up OpsIntel and creates `data/setup-key.txt` on the server computer. Open that file locally and copy its contents into One-time setup key. The key is not displayed by the website.
5. Choose the first administrator's username, name and password. Usernames are case-insensitive and use 3-80 letters/numbers/dots/underscores/@/hyphens. Passwords require at least 15 characters and accept spaces; use a unique passphrase. Confirm the password and create the administrator.
6. The setup key is single-use and is deleted after setup when the operating system permits. Even if the file remains, setup is disabled once an account exists. Sign in with your chosen credentials.

The first administrator can access all existing projects. Existing payloads are retained; there is no need to re-upload data or recreate mappings, targets or findings. On subsequent upgrades that retain the account database, sign in with your existing account instead of repeating setup.

## Roles

| Role | Project access | Shared changes | Account administration |
| --- | --- | --- | --- |
| Administrator | All projects, including older projects | All project functions | Create/manage users, reset passwords and assign project access |
| Analyst | Assigned projects and projects they create | Only projects assigned Edit permission | Own password only |
| Viewer | Projects explicitly assigned View permission | No shared changes | Own password only |

Analysts can create projects and receive Edit access to their new projects. An analyst assigned View permission behaves as a reader on that project. Viewers cannot create projects or receive Edit permission. New non-administrator accounts have no access to existing projects until assigned. Promoting a user to Administrator grants access to every project; treat that as a privileged action.

Read-only project users can use Command Centre filters, explore KPIs, read target alerts, read/export reports and view/export audit history. They cannot upload data, clean data, apply mappings, create findings, edit shared report text or save targets. Data Workspace and Investigation are available to project editors. Read permission covers the project's data and findings, including findings JSON exports; only approved findings appear in PDFs.

Permission checks run in the data layer as well as the interface. Session roles are read from the account database; browser-entered role names are not trusted as authorization.

## Add a colleague

1. Sign in as an administrator and open Account & access in the sidebar.
2. Under Create a user, choose a username, display name, role and unique temporary password. Give credentials to the intended user through your normal trusted channel; OpsIntel does not send messages or email.
3. Under Manage user, select that user.
4. Under Project permissions, select a project and choose View or Edit. Save the permission. Repeat for other projects as needed. Administrator accounts already have access to all projects.
5. The user must replace their temporary password before accessing projects. After changing it, they sign in again with their new password.

To remove access, select No access for the relevant project. To disable an account or change its role, use Save account changes. Account changes and password resets revoke that user's existing sessions. Permission changes are checked at the next app interaction or storage action. Content already displayed in a browser or already downloaded cannot be recalled. At least one active administrator must remain.

## Sign-in and password behavior

- Passwords are stored as per-password salted PBKDF2-HMAC-SHA256 hashes with 600,000 iterations. Plaintext passwords are not stored in project payloads or logs. This work factor follows the [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- Five failed attempts for the same normalized username within five minutes trigger a five-minute sign-in cooldown. Errors do not reveal whether an account exists. An administrator's password reset clears that account's cooldown.
- Sessions expire after 30 minutes without app interaction or eight hours from sign-in. Sign-out invalidates that session and clears its server-side project/draft state. Password changes, resets and account role/active changes revoke all sessions for that user.
- Sign-in is tied to the current Streamlit session. A full browser refresh, reconnect, server restart or new tab can require signing in again. There is no persistent remember-me cookie. See the [Streamlit session-state documentation](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state).
- Security activity is separate from project audit history. Administrators can view/export the latest 2,000 security events in Account & access. Older events remain in SQLite. Passwords, setup keys and session tokens are not included in event records.

## Concurrent project edits

The app remembers each person's last-opened accessible project. Viewing a project does not update its saved data revision. Editors' changes continue to save automatically.

If another session saves a newer version, a stale session cannot overwrite it. A message asks you to export any unsaved work, then open Reload latest saved version, check Discard my unsaved changes and press Reload saved project. Reload discards that session's local draft and opens the saved version. A reader can also reload to see another user's changes. Conflict handling does not merge competing edits automatically.

## Forgotten password

If another administrator is available, ask them to reset the account's password in Account & access. The user must change the temporary password at the next sign-in.

If the only administrator has forgotten their password, the trusted owner of the server computer can use offline recovery:

1. Stop OpsIntel and open a terminal in the app folder.
2. Run:

       python manage_users.py reset-password --username your_username

3. Enter and confirm a new password when prompted. It is not shown on screen or included in the command line.
4. Restart OpsIntel and sign in with the new password.

Offline recovery needs local access to the application and database folder, is logged, and revokes the account's sessions. It does not change roles or reactivate disabled accounts. There is no web-facing password-recovery shortcut or unauthenticated administrator API.

## Storage, backups and deployment scope

Accounts, salted hashes, hashed session identifiers, project memberships, last-opened project preferences, security events and project payloads live in the same local `data/opsintel.sqlite3` file. Back up the entire `data` folder while the app is stopped. Moving that folder moves accounts and permissions too. Keep it private; application login does not encrypt SQLite, protect the folder from the computer's owner or secure copies exported from the app.

This download defaults to listening on `127.0.0.1`, for access from the server computer. Sharing it requires an explicit server-address change and a correctly configured HTTPS deployment. Keep all Streamlit routes behind an access-controlled gateway for remote use. Streamlit-native download URLs are bearer links; knowledge of an existing link can permit downloading its file, and revoking an app session does not revoke previously generated download links. Do not use generated download links as permission-controlled sharing links. This release does not add SSO, MFA, an encrypted database or protection from an attacker who controls the server's filesystem. Use a deployment with suitable identity and file-delivery controls for sensitive shared data.

Do not disable Streamlit's CORS/XSRF protections. Hosted platforms with temporary disks need persistent storage for accounts and projects. The local account system is an application access layer, not a replacement for secure hosting or OS access controls.
