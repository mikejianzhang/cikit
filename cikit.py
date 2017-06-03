from cikit.ciutils.cmdutils import CMDExecutor

if __name__ == "__main__":
    try:
        cmd = CMDExecutor("","/Users/mike/Documents/MikeWorkspace/FreessureCoffee/service")
        output = cmd.execute()
    except Exception as err:
        print err
    else:
        print output