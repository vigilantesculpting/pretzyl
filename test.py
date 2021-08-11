#!/usr/bin/env python

import sys
import pretzyl

import traceback
import pdb

#######################################################################
# Some simple unit test code follows:

def testexpr(p, expr, expected = [True], tolist = False, Exc = None):
	print "-------------------------"
	if Exc is None:
		print "testing expr <%s>, tolist %s, expected <%s>" % (expr, tolist, expected)
	else:
		print "testing expr <%s>, tolist %s, exception %s" % (expr, tolist, Exc)
	try:
		d = p.eval(expr, count = None)
	except Exception as e:
		assert(Exc is not None and isinstance(e, Exc))
		print "got expected exception", Exc
		return True
	if tolist:
		d = [list(i) for i in d]
	assert(d == expected)
	print "got expected result", expected

def test():

	#pretzyl.LOG = True

	env = {
		'name': 'Jack',
		'key': 'a7c34bd',
		'setbutFalse': False,
		'testlist': ['one', 'two', 'three'],
		'testdict': {'one': 'ONE', 'two': 'TWO', 'three': 'THREE'},
	}

	p = pretzyl.Pretzyl(env)

	# test simple unary operators

	# -
	testexpr(p, "True", [True])
	testexpr(p, "False", [False])
	testexpr(p, "1", [1])
	testexpr(p, "1 2 3", [1, 2, 3])
	testexpr(p, "(1 2 3)", [[1, 2, 3]])
	testexpr(p, "3.14", [3.14])

	# exists
	testexpr(p, "jack exists", [False])
	testexpr(p, "setbutFalse exists", [True])
	testexpr(p, "name exists", [True])

	# not
	testexpr(p, "name not", [False])
	testexpr(p, "setbutFalse not", [True])
	testexpr(p, "False not", [True])
	testexpr(p, "True not", [False])
	testexpr(p, "None not", [True])

	# isnone
	testexpr(p, "None isnone", [True])
	testexpr(p, "True isnone", [False])
	testexpr(p, "False isnone", [False])

	# makeref
	testexpr(p, "'n' 'ame' + makeref", ["Jack"])

	# makeop
	testexpr(p, "4 5 'sum' makeop", [9])

	# length
	testexpr(p, "(1 2 3) length", [3])
	testexpr(p, "'hello world!' length", [12])

	# dup
	testexpr(p, "'hello' dup", ['hello', 'hello'])
	testexpr(p, "(1 2 3) dup", [[1, 2, 3], [1, 2, 3]])

	# unpack
	testexpr(p, "(1 2 3) unpack", [1, 2, 3])
	# enpack
	testexpr(p, "1 2 3 enpack", [[1, 2, 3]])

	# int
	testexpr(p, "3.14 int", [3])
	testexpr(p, "3.00 int", [3])

	# str
	testexpr(p, "3.14 str", ["3.14"])
	testexpr(p, "3.00 str", ["3.0"])

	# enumerate
	testexpr(p, "testlist enumerate", [[(0, 'one'), (1, 'two'), (2, 'three')]], tolist = True)

	# range
	testexpr(p, "10 range", [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]])

	# iteritems
	testexpr(p, "testdict iteritems", [[('three', 'THREE'), ('two', 'TWO'), ('one', 'ONE')]], tolist = True)

	# ceil
	testexpr(p, "1.5 ceil", [2.0])
	testexpr(p, "-1.5 ceil", [-1.0])
	# floor
	testexpr(p, "1.5 floor", [1.0])
	testexpr(p, "-1.5 floor", [-2.0])

	# booleans logic
	testexpr(p, "5 4 <", [False])
	testexpr(p, "4 5 <")
	testexpr(p, "5 4 < !")
	testexpr(p, "5 4 >=")

	# arithmetic
	testexpr(p, "2 2 2 sum 4 *", [24])
	testexpr(p, "2 (2 2 sum) 4 prod", [32]) # also tests <"mul" repeat>
	testexpr(p, "4 *2", [16])
	testexpr(p, "4 4 **", [256])

	# add
	testexpr(p, "14 5 +", [19])
	testexpr(p, "14.0 5 +", [19.0])
	# sub
	testexpr(p, "14 5 -", [9])
	testexpr(p, "14.0 5 -", [9.0])
	# mul
	testexpr(p, "14 5 *", [70])
	testexpr(p, "14.0 5 *", [70.0])
	# div
	testexpr(p, "14 5 /", [2.8])
	testexpr(p, "14 5 //", [2])
	testexpr(p, "14.0 5 //", [2.8])
	# ceil
	testexpr(p, "2.8 ^", [3.0])
	testexpr(p, "14 5 /^", [3.0])
	testexpr(p, "14 5 /^ int", [3])

	# at
	testexpr(p, "('jack' 'suzy' 'mary') 2 <>", ["mary"])

	# contains
	testexpr(p, "('jack' 'suzy' 'mary') 'mary' contains")
	testexpr(p, "('jack' 'suzy' 'mary') 'sarah' contains", [False])

	# slice, startslice, endslice
	testexpr(p, "('jack' 'suzy' 'mary' 'sarah') 2 [:", [['mary', 'sarah']])
	testexpr(p, "('jack' 'suzy' 'mary' 'sarah') 2 :]", [['jack', 'suzy']])
	testexpr(p, "('jack' 'suzy' 'mary' 'sarah') 1 3 []", [['suzy', 'mary']])
	# splitat
	testexpr(p, "('jack' 'suzy' 'mary' 'sarah') 1 splitat", [['jack'], ['suzy', 'mary', 'sarah']])
	# swap
	testexpr(p, "('jack' 'suzy' 'mary' 'sarah') 1 splitat swap", [['suzy', 'mary', 'sarah'], ['jack']])
	# combo double punch
	testexpr(p, "'jack' 'suzy' 'mary' enpack 1 splitat swap", [['suzy', 'mary'], ['jack']])

	# groupby (and generator) test:
	testexpr(p, "(1 2 3 4 5 6 7 8) 3 {}", [[[1, 2, 3], [4, 5, 6], [7, 8]]], tolist = True)

	# filename generation (pathsum and sum)
	testexpr(p, "'static' 'css' ('site-' key '.html' sum) //+", ["static/css/site-a7c34bd.html"])

	# sum on text
	testexpr(p, "'static' 'css' ('site-' key '.html' sum) //+", ["static/css/site-a7c34bd.html"])

	# repeat
	testexpr(p, "1 2 3 4 5 6 7 8 9 10 'add' repeat", [55]) 

	# the cake is a lie
	testexpr(p, "cake", Exc=pretzyl.InvalidReference)

	# these all look like operators, but they should
	# be rejected since each one has a syntax error.
	# This results in a lookup failure (ie. KeyError in the environment)
	testexpr(p, "2 2 *%", 	Exc=pretzyl.InvalidReference)
	testexpr(p, "2 2 **x", 	Exc=pretzyl.InvalidReference)
	testexpr(p, "2 2 ***", 	Exc=pretzyl.InvalidReference)
	testexpr(p, "2 2 +#", 	Exc=pretzyl.InvalidReference)
	testexpr(p, "2 2 $$", 	Exc=pretzyl.InvalidReference)

	# syntax errors - mismatched brackets
	testexpr(p, "( ( )", 		Exc=pretzyl.NestingException)
	testexpr(p, "( ( ) ) )", 	Exc=pretzyl.NestingException)

	# the + operator expects two arguments, but there is only one
	testexpr(p, "highlander +", Exc=pretzyl.StackUnderflow)
	# artificially lower the stack limit, then feed the parser a large stack
	p.STACKLIMIT = 10
	testexpr(p, "0 1 2 3 4 5 6 7 8 9 10", Exc=pretzyl.StackOverflow)
	# artificially lower the stack depth, then feed the parser a deep nesting of scopes
	p.STACKDEPTH = 5
	testexpr(p, "( ( ( ( ( ( ) ) ) ) ) )", Exc=pretzyl.RecursionOverflow)
	
	## artificially lower the iteration limit, then feed the parser a big squash
	#p.INFLIMIT = 5
	#testException(p, pretzyl.IterationOverflow, "0 1 2 3 4 5 6 sum")

	return 0

if __name__ == "__main__":
	try:
		result = test()
	except:
		traceback.print_exc()
		pdb.post_mortem()
	sys.exit(result)
