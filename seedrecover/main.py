"""Command line interface including input and output.

TODO keyderiv.py: stake key from master key

TODO stakecheck.py: Check for plausible structure of given addresses
TODO order.py: Avoid repetitions of same seed phrases
TODO Byron, Ledger, and Trezor support
TODO Multi-account support
"""
import argparse
import sys

from seedrecover.wordlist import Wordlist
from seedrecover.order import iterate
from seedrecover.keyderiv import seed_to_stakeaddress, ChecksumError
from seedrecover.stakecheck import StakeAddresses
from seedrecover.bfstakecheck import BlockFrost, InactiveError

from typing import Optional


def parse_args() -> argparse.Namespace:
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("seed", nargs="*",
                        help="known words of seed phrase", metavar="WORD")
    parser.add_argument("-w", "--wordlist",
                        help="wordlist to use (default: english)",
                        metavar="FILE")
    parser.add_argument("-s", "--similar", type=int, default=0,
                        help="try similar words up to edit distance",
                        metavar="EDIT DISTANCE")
    parser.add_argument("-o", "--order", default=False, action="store_true",
                        help="try different orders of seed words")
    parser.add_argument("-l", "--length", type=int,
                        help="length of seed phrase", metavar="LENGTH")
    parser.add_argument("-m", "--missing", type=int, nargs="+", default=[],
                        help="missing word positions", metavar="POSITION")
    parser.add_argument("-a", "--address", nargs="+", default=[],
                        help="check for stake addresses",
                        metavar="ADDRESS")
    parser.add_argument("-b", "--blockfrost",
                        help="check on BlockFrost", metavar="API KEY")
    return parser.parse_args()


def get_seed(wordlist: Wordlist, known: list[str],
             similar: int) -> list[list[str]]:
    """Determine possible seed words from given known words."""
    seed = []
    for word in known:
        if not wordlist.contains(word):
            print(f"'{word}' not in wordlist!", file=sys.stderr)
        words = wordlist.get_words(word, similar)
        print(f"{word} => {', '.join(words)}", file=sys.stderr)
        seed.append(words)
    return seed


def get_length(length: Optional[int], known: int) -> int:
    """Determine length of seed phrase to search for."""
    if not length:
        print("Length not set. Using smallest length for given phrase.",
              file=sys.stderr)
        length = known
        if known % 3:
            length += 3 - known % 3
    if length % 3 != 0:
        print("Length is not a multiple of 3!", file=sys.stderr)
        exit(1)
    if known > length:
        print("More known words than length given!", file=sys.stderr)
        exit(1)
    print(f"{length - known} of {length} words missing.", file=sys.stderr)
    return length


def get_missing_positions(given: list[int], length: int,
                          missing: int) -> list[int]:
    """Check or determine positions for missing words."""
    missing_positions = [i-1 for i in given]
    if not missing_positions:
        missing_positions = list(range(length))
    if len(missing_positions) < missing:
        print(f"Only {len(missing_positions)} positions given"
              " for missing words!", file=sys.stderr)
        exit(1)
    return missing_positions


def main() -> None:
    """Execute the main control flow of the seedrecover script."""
    args = parse_args()
    wordlist = Wordlist(args.wordlist)
    seed = get_seed(wordlist, args.seed, args.similar)
    length = get_length(args.length, len(seed))
    missing_positions = get_missing_positions(args.missing, length,
                                              length - len(seed))
    sc = None
    if args.key:
        sc = StakeAddresses(args.address)
    bf = None
    if args.blockfrost:
        try:
            bf = BlockFrost(args.blockfrost)
        except InactiveError as e:
            print(e, file=sys.stderr)
            bf = None
    already_checked = set()
    total_seed_phrases = 0
    checksum_seed_phrases = 0
    norepeat_seed_phrases = 0
    for seed_phrase in iterate(seed, args.order, wordlist,
                               length, missing_positions):
        total_seed_phrases += 1
        try:
            stake_address = seed_to_stakeaddress(seed_phrase, wordlist)
        except ChecksumError:
            continue
        checksum_seed_phrases += 1
        if stake_address in already_checked:
            continue
        already_checked.add(stake_address)
        norepeat_seed_phrases += 1
        searched = False
        active = False
        verbose = True
        if sc:
            if sc.check_stake_address(stake_address):
                searched = True
            verbose = False
        if bf:
            try:
                if bf.check_stake_address(stake_address):
                    active = True
                verbose = False
            except InactiveError as e:
                print(e, file=sys.stderr)
                bf = None
        if searched and active:
            print("Searched and active stake address found:")
        elif searched:
            print("Searched stake address found:")
        elif active:
            print("Active stake address found:")
        if searched or active or verbose:
            print(f"{stake_address}: {' '.join(seed_phrase)}")
    print(f"{total_seed_phrases:10_} seed phrases checked.", file=sys.stderr)
    print(f"{checksum_seed_phrases:10_} fulfilled checksum.", file=sys.stderr)
    print(f"{norepeat_seed_phrases:10_} without repetitions.", file=sys.stderr)
