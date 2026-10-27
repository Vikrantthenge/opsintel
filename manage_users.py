"""Offline password recovery for the trusted owner of the local data folder."""
import argparse
from getpass import getpass
from security import AuthStore,password_record


def main():
 parser=argparse.ArgumentParser(description='Reset a local OpsIntel password from the server computer. Stop OpsIntel first.')
 parser.add_argument('action',choices=['reset-password'])
 parser.add_argument('--username',required=True)
 args=parser.parse_args()
 password=getpass('New password (at least 15 characters): ')
 confirm=getpass('Confirm new password: ')
 if password!=confirm:raise SystemExit('Passwords do not match. Nothing changed.')
 try:record=password_record(password)
 except ValueError as exc:raise SystemExit(str(exc)) from None
 store=AuthStore()
 with store.connect() as con:
  con.execute('BEGIN IMMEDIATE')
  user=con.execute('SELECT id,username FROM users WHERE username=?',(args.username.strip().casefold(),)).fetchone()
  if not user:raise SystemExit('Account not found. Nothing changed.')
  con.execute('UPDATE users SET password=?,must_change=0 WHERE id=?',(record,user['id']))
  con.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
  con.execute('DELETE FROM login_attempts WHERE username=?',(user['username'],))
  store.event(con,'local-folder-owner','Offline password reset; revoked sessions',user['username'])
 print('Password updated. Existing sessions were revoked. Start OpsIntel and sign in with the new password.')


if __name__=='__main__':main()
