from cikit.cibuild import CIBuild

if __name__ == "__main__":
    try:

        build = CIBuild("/Users/mike/Documents/MikeWorkspace/FreessureCoffee/service", "1.3.1", "service")
        output = build.getCurrentCommit()
        print output
    except Exception as err:
        print err