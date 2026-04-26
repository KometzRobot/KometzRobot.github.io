#!/usr/bin/env python3
"""
Password & Security Tool — Professional Gig Product
Generates secure passwords, passphrases, PINs. Checks password strength.
Zero external dependencies.
Built by KometzRobot / Meridian AI

Usage:
  python3 password-generator.py --count 10 --length 16
  python3 password-generator.py --passphrase --words 5
  python3 password-generator.py --check "MyP@ssw0rd"
  python3 password-generator.py --pin 6
  python3 password-generator.py --bulk 100 --length 20 --output passwords.txt
"""

import argparse
import math
import os
import string
import hashlib


# Common weak passwords to check against
COMMON_PASSWORDS = {
    'password', '123456', '12345678', 'qwerty', 'abc123', 'monkey', 'master',
    'dragon', 'login', 'letmein', 'welcome', 'shadow', 'sunshine', 'trustno1',
    'iloveyou', 'batman', 'access', 'hello', 'charlie', 'password1', '123456789',
}

# Word list for passphrases
WORDLIST = [
    'apple', 'brave', 'cloud', 'dance', 'eagle', 'flame', 'grape', 'house',
    'ivory', 'jewel', 'karma', 'lemon', 'maple', 'night', 'ocean', 'pearl',
    'quest', 'river', 'storm', 'tiger', 'ultra', 'vivid', 'waltz', 'xenon',
    'yacht', 'zebra', 'amber', 'blaze', 'coral', 'delta', 'ember', 'frost',
    'gleam', 'haven', 'index', 'joust', 'knack', 'lunar', 'merit', 'noble',
    'orbit', 'prism', 'quilt', 'ridge', 'sable', 'torch', 'unity', 'vault',
    'widow', 'pixel', 'yield', 'zenith', 'arrow', 'brass', 'chess', 'diver',
    'epoch', 'forge', 'ghost', 'hymn', 'ionic', 'jazzy', 'kneel', 'lodge',
    'mocha', 'nexus', 'ozone', 'plume', 'quirky', 'raven', 'scope', 'trail',
    'umbra', 'venom', 'wrath', 'xerox', 'youth', 'zonal', 'acorn', 'birch',
    'cider', 'dusk', 'elm', 'fable', 'glow', 'haste', 'iris', 'jade',
    'kite', 'lily', 'myth', 'neon', 'olive', 'pine', 'quota', 'rush',
    'silk', 'thorn', 'umber', 'vine', 'wheat', 'xylem', 'yawn', 'zinc',
]


def secure_random_int(max_val):
    """Generate a cryptographically secure random integer."""
    random_bytes = os.urandom(4)
    return int.from_bytes(random_bytes, 'big') % max_val


def generate_password(length=16, uppercase=True, lowercase=True, digits=True, symbols=True, exclude=''):
    """Generate a secure random password."""
    chars = ''
    required = []

    if lowercase:
        pool = string.ascii_lowercase
        for c in exclude:
            pool = pool.replace(c, '')
        chars += pool
        if pool:
            required.append(pool[secure_random_int(len(pool))])

    if uppercase:
        pool = string.ascii_uppercase
        for c in exclude:
            pool = pool.replace(c, '')
        chars += pool
        if pool:
            required.append(pool[secure_random_int(len(pool))])

    if digits:
        pool = string.digits
        for c in exclude:
            pool = pool.replace(c, '')
        chars += pool
        if pool:
            required.append(pool[secure_random_int(len(pool))])

    if symbols:
        pool = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        for c in exclude:
            pool = pool.replace(c, '')
        chars += pool
        if pool:
            required.append(pool[secure_random_int(len(pool))])

    if not chars:
        chars = string.ascii_letters + string.digits

    # Fill remaining length
    remaining = length - len(required)
    password_chars = required + [chars[secure_random_int(len(chars))] for _ in range(max(0, remaining))]

    # Shuffle using Fisher-Yates
    for i in range(len(password_chars) - 1, 0, -1):
        j = secure_random_int(i + 1)
        password_chars[i], password_chars[j] = password_chars[j], password_chars[i]

    return ''.join(password_chars)


def generate_passphrase(words=4, separator='-', capitalize=True):
    """Generate a memorable passphrase."""
    selected = []
    for _ in range(words):
        word = WORDLIST[secure_random_int(len(WORDLIST))]
        if capitalize:
            word = word.capitalize()
        selected.append(word)

    return separator.join(selected)


def generate_pin(length=4):
    """Generate a numeric PIN."""
    return ''.join(str(secure_random_int(10)) for _ in range(length))


def check_strength(password):
    """Analyze password strength."""
    score = 0
    feedback = []

    # Length
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1
    if len(password) < 8:
        feedback.append("Too short (minimum 8 characters)")

    # Character variety
    has_lower = any(c in string.ascii_lowercase for c in password)
    has_upper = any(c in string.ascii_uppercase for c in password)
    has_digit = any(c in string.digits for c in password)
    has_symbol = any(c in string.punctuation for c in password)

    variety = sum([has_lower, has_upper, has_digit, has_symbol])
    score += variety

    if not has_upper:
        feedback.append("Add uppercase letters")
    if not has_digit:
        feedback.append("Add numbers")
    if not has_symbol:
        feedback.append("Add symbols")

    # Common password check
    if password.lower() in COMMON_PASSWORDS:
        score = 0
        feedback.append("This is a commonly used password!")

    # Sequential/repeated characters
    for i in range(len(password) - 2):
        if password[i] == password[i+1] == password[i+2]:
            score -= 1
            feedback.append("Avoid repeated characters")
            break

    # Entropy calculation
    charset_size = 0
    if has_lower:
        charset_size += 26
    if has_upper:
        charset_size += 26
    if has_digit:
        charset_size += 10
    if has_symbol:
        charset_size += 32

    entropy = len(password) * math.log2(max(charset_size, 1))

    # Rating
    if score >= 6:
        rating = "EXCELLENT"
    elif score >= 4:
        rating = "GOOD"
    elif score >= 2:
        rating = "FAIR"
    else:
        rating = "WEAK"

    return {
        'rating': rating,
        'score': f"{score}/7",
        'length': len(password),
        'entropy': f"{entropy:.1f} bits",
        'has_lowercase': has_lower,
        'has_uppercase': has_upper,
        'has_digits': has_digit,
        'has_symbols': has_symbol,
        'feedback': feedback or ["Strong password!"],
    }


def main():
    parser = argparse.ArgumentParser(description='Password & Security Tool')
    parser.add_argument('--length', type=int, default=16, help='Password length')
    parser.add_argument('--count', type=int, default=1, help='Number of passwords')
    parser.add_argument('--passphrase', action='store_true', help='Generate passphrase')
    parser.add_argument('--words', type=int, default=4, help='Words in passphrase')
    parser.add_argument('--pin', type=int, help='Generate PIN of N digits')
    parser.add_argument('--check', help='Check password strength')
    parser.add_argument('--no-symbols', action='store_true', help='Exclude symbols')
    parser.add_argument('--no-uppercase', action='store_true', help='Exclude uppercase')
    parser.add_argument('--exclude', default='', help='Characters to exclude')
    parser.add_argument('--separator', default='-', help='Passphrase separator')
    parser.add_argument('--output', help='Output file')
    parser.add_argument('--bulk', type=int, help='Generate bulk passwords')

    args = parser.parse_args()

    results = []

    if args.check:
        strength = check_strength(args.check)
        print(f"\nPassword Strength Analysis")
        print(f"{'='*40}")
        for key, value in strength.items():
            if key == 'feedback':
                print(f"  {'Feedback':>15}:")
                for item in value:
                    print(f"  {'':>15}  - {item}")
            else:
                print(f"  {key:>15}: {value}")
        return

    count = args.bulk or args.count

    for i in range(count):
        if args.pin:
            pw = generate_pin(args.pin)
        elif args.passphrase:
            pw = generate_passphrase(args.words, args.separator)
        else:
            pw = generate_password(
                length=args.length,
                symbols=not args.no_symbols,
                uppercase=not args.no_uppercase,
                exclude=args.exclude,
            )
        results.append(pw)

        if not args.output and count <= 20:
            strength = check_strength(pw)
            print(f"  {pw}  [{strength['rating']}] {strength['entropy']}")

    if args.output:
        with open(args.output, 'w') as f:
            for pw in results:
                f.write(pw + '\n')
        print(f"Saved {len(results)} passwords to {args.output}")
    elif count > 20:
        print(f"Generated {count} passwords. Use --output to save.")
        for pw in results[:5]:
            print(f"  {pw}")
        print(f"  ... and {count - 5} more")


if __name__ == '__main__':
    main()
