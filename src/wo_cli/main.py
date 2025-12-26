# src/wo_cli/main.py
import argparse

def main():
    parser = argparse.ArgumentParser(description="Worked-Example CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Worked-example command
    parser_we = subparsers.add_parser("worked-example", help="Display a worked example")
    parser_we.add_argument("topic", type=str, help="The topic for the worked example")

    # Completion-problem command
    parser_cp = subparsers.add_parser("completion-problem", help="Display a completion problem")
    parser_cp.add_argument("topic", type=str, help="The topic for the completion problem")

    args = parser.parse_args()

    if args.command == "worked-example":
        print(f"Displaying worked example for: {args.topic}")
    elif args.command == "completion-problem":
        print(f"Displaying completion problem for: {args.topic}")

if __name__ == "__main__":
    main()
