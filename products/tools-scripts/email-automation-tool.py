#!/usr/bin/env python3
"""
Email Automation Tool — Professional Gig Product
Automates bulk email operations: send newsletters, auto-respond, filter, organize.
Built by KometzRobot / Meridian AI

Usage:
  python3 email-automation-tool.py --help
"""

import argparse
import csv
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import json
import os
from datetime import datetime


def send_newsletter(smtp_host, smtp_port, username, password, csv_file, subject, body_template, use_tls=True):
    """Send personalized emails to a CSV list of recipients."""
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        recipients = list(reader)

    print(f"Sending to {len(recipients)} recipients...")

    if use_tls:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP(smtp_host, smtp_port)

    server.login(username, password)

    sent = 0
    failed = 0
    for recipient in recipients:
        try:
            personalized_body = body_template
            for key, value in recipient.items():
                personalized_body = personalized_body.replace(f"{{{{{key}}}}}", value)

            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = recipient.get('email', '')
            msg['Subject'] = subject
            msg.attach(MIMEText(personalized_body, 'plain'))

            server.sendmail(username, recipient['email'], msg.as_string())
            sent += 1
            print(f"  Sent to {recipient['email']}")
            time.sleep(1)  # Rate limiting
        except Exception as e:
            failed += 1
            print(f"  FAILED: {recipient.get('email', 'unknown')} — {e}")

    server.quit()
    print(f"\nDone: {sent} sent, {failed} failed")


def auto_responder(imap_host, imap_port, smtp_host, smtp_port, username, password, rules_file):
    """Auto-respond to emails based on keyword rules."""
    with open(rules_file, 'r') as f:
        rules = json.load(f)

    imap = imaplib.IMAP4_SSL(imap_host, imap_port) if imap_port == 993 else imaplib.IMAP4(imap_host, imap_port)
    imap.login(username, password)
    imap.select('INBOX')

    _, messages = imap.search(None, 'UNSEEN')
    if not messages[0]:
        print("No new messages.")
        return

    ids = messages[0].split()
    print(f"Processing {len(ids)} new emails...")

    smtp = smtplib.SMTP(smtp_host, smtp_port)
    smtp.login(username, password)

    for mid in ids:
        _, data = imap.fetch(mid, '(RFC822)')
        msg = email.message_from_bytes(data[0][1])
        subject = str(msg['Subject'] or '')
        sender = str(msg['From'] or '')

        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode(errors='replace')
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors='replace')

        for rule in rules:
            keyword = rule['keyword'].lower()
            if keyword in subject.lower() or keyword in body.lower():
                reply = MIMEText(rule['response'])
                reply['Subject'] = f"Re: {subject}"
                reply['From'] = username
                reply['To'] = sender
                smtp.sendmail(username, sender, reply.as_string())
                print(f"  Auto-replied to {sender} (matched: {keyword})")
                break

    smtp.quit()
    imap.logout()


def organize_inbox(imap_host, imap_port, username, password, rules):
    """Organize inbox by moving emails to folders based on rules."""
    imap = imaplib.IMAP4_SSL(imap_host, imap_port) if imap_port == 993 else imaplib.IMAP4(imap_host, imap_port)
    imap.login(username, password)
    imap.select('INBOX')

    moved = 0
    for rule in rules:
        keyword = rule['keyword']
        folder = rule['folder']

        # Create folder if it doesn't exist
        imap.create(folder)

        _, messages = imap.search(None, f'SUBJECT "{keyword}"')
        if messages[0]:
            for mid in messages[0].split():
                imap.copy(mid, folder)
                imap.store(mid, '+FLAGS', '\\Deleted')
                moved += 1

    imap.expunge()
    imap.logout()
    print(f"Organized: {moved} emails moved")


def export_contacts(imap_host, imap_port, username, password, output_file):
    """Export unique email contacts from inbox to CSV."""
    imap = imaplib.IMAP4_SSL(imap_host, imap_port) if imap_port == 993 else imaplib.IMAP4(imap_host, imap_port)
    imap.login(username, password)
    imap.select('INBOX')

    _, messages = imap.search(None, 'ALL')
    contacts = set()

    for mid in messages[0].split():
        _, data = imap.fetch(mid, '(RFC822)')
        msg = email.message_from_bytes(data[0][1])
        sender = msg['From']
        if sender:
            # Extract email from "Name <email>" format
            if '<' in sender:
                addr = sender.split('<')[1].rstrip('>')
            else:
                addr = sender
            contacts.add(addr.strip())

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['email'])
        for contact in sorted(contacts):
            writer.writerow([contact])

    imap.logout()
    print(f"Exported {len(contacts)} unique contacts to {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Email Automation Tool')
    parser.add_argument('action', choices=['newsletter', 'autorespond', 'organize', 'export'],
                       help='Action to perform')
    parser.add_argument('--smtp-host', default='smtp.gmail.com')
    parser.add_argument('--smtp-port', type=int, default=587)
    parser.add_argument('--imap-host', default='imap.gmail.com')
    parser.add_argument('--imap-port', type=int, default=993)
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--csv', help='CSV file with recipients')
    parser.add_argument('--subject', help='Email subject')
    parser.add_argument('--body', help='Email body template (use {{column_name}} for personalization)')
    parser.add_argument('--rules', help='JSON rules file')
    parser.add_argument('--output', help='Output file')

    args = parser.parse_args()

    if args.action == 'newsletter':
        send_newsletter(args.smtp_host, args.smtp_port, args.username, args.password,
                       args.csv, args.subject, args.body)
    elif args.action == 'autorespond':
        auto_responder(args.imap_host, args.imap_port, args.smtp_host, args.smtp_port,
                      args.username, args.password, args.rules)
    elif args.action == 'export':
        export_contacts(args.imap_host, args.imap_port, args.username, args.password,
                       args.output or 'contacts.csv')
