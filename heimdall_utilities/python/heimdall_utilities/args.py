"""
Utility methods.

License: public domain.

Use print_usage and parse_args to read in args in your python program:
Example:
    args = {
        "-m":{"type":str,   "default":None, "desc":"Model name."},
        "-n":{"type":str,   "default":"",   "desc":"Name of model in world."},
        "-x":{"type":float, "default":0.0,  "desc":"X location"},
    }
    if not parse_args(sys.argv, args):
        print_usage(sys.argv, args)
        exit(1)
"""

def print_usage(argv, args_specs):
    print "Usage: %s [OPTIONS]" % argv[0]
    print "Arguments:"
    for arg, value in args_specs.iteritems():
        print "    %s VALUE: %s" % (arg, value["desc"])
        print "        default: %s" % str(value["default"])
    print "Example:"
    print "rosrun <package> <binary/script>", 
    for arg, value in args_specs.iteritems():
        val = str(value["default"])
        if val == "False":
            val = "0"
        if val == "True":
            val = "1"
        print "%s %s" % (arg, val),

def parse_args(argv, args_specs):
    #Parse arguments:
    key = None
    for arg in argv[1:]:
        if arg == "-h":
            return False
        if not key == None: 
            if key in args_specs:
                if "value" in args_specs[key]:
                    print "ERROR: Argument \"%s\" is already specified!" % key
                    return False
                try:
                    args_specs[key]["value"] = args_specs[key]["type"](arg)
                    if args_specs[key]["type"] == bool:
                        assert arg in ["1", "0"]
                        args_specs[key]["value"] = int(arg) == 1
                except AssertionError, ValueError:
                    print "ERROR: Invalid type specified for argument: \"%s\"!" % key
                    return False
            else:
                print "ERROR: Unknown argument \"%s\" specified!" % key
                return False
            key = None
        else:
            key = arg
    if not key == None:
        print "ERROR: No value specified for argument \"%s\"!" % key
        return False
    #Set default values if arguments are not set:
    for arg, value in args_specs.iteritems():
        #Fail if no default is available:
        if not "value" in args_specs[arg] and args_specs[arg]["default"] == None:
            print "ERROR: Argument %s not set and has no default value!" % arg
            return False
        if not "value" in args_specs[arg]:
            args_specs[arg]["value"] = args_specs[arg]["default"]
    return True



