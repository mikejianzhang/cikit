from cikit.cibuild import CIBuild

if __name__ == "__main__":
    try:

        build = CIBuild("/Users/mike/Documents/MikeWorkspace/FreessureCoffee/service", "1.3.1", "service")
        #build.createLabel("1.3.1_b3", "aee8946052d540b4db278acc9295b40c3538cd41")
        #print build.getNextBuildNumber()
        build.prebuild(True)
    except Exception as err:
        print err