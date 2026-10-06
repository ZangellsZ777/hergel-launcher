import sys

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from hergel.selftest import main
        raise SystemExit(main(sys.argv[2]))
    from hergel.gui import main
    main()
