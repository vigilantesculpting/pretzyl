#!/usr/bin/env python

import sys
import pretzyl

import traceback
import pdb

#######################################################################
# Some simple unit test code follows:

def test():

	env = {
		'name': 'Jack',
		'key': 'a7c34bd',
	}

	p = pretzyl.Pretzyl(env)

	d = p.eval("('jack' 'suzy' 'mary') 2 <>")
	print d
	assert(d == "mary")

	d = p.eval("('jack' 'suzy' 'mary') 1 None []")
	d = list(d)
	print d
	assert(d == ['suzy', 'mary'])

	pdb.set_trace()
	# a simple arithmetic expression
	d = p.eval("2 2 2 sum 4 *")
	print d
	assert(d == 24)

	# a nested arithmetic expression
	d = p.eval("2 (2 2 sum) 4 *")
	print d
	assert(d == 16)

	# more arithmetic...
	d = p.eval("4 *2")
	print d
	assert(d == 16)

	d = p.eval("4 4 **")
	print d
	assert(d == 256)

	# string manipulation
	d = p.eval("   'hello [' name  ']!' + 2 times")
	print d
	assert(d == "hello [Jack]!")

	# basic booleans
	d = p.eval("True")
	print d
	assert(d == True)

	# more booleans
	d = p.eval("5 4 <")
	print d
	assert(d == False)

	d = p.eval("4 5 <")
	print d
	assert(d == True)

	d = p.eval("5 4 < !")
	print d
	assert(d == True)

	d = p.eval("5 4 >=")
	print d
	assert(d == True)

	# create a ref from a string, this will evaluate it and look it up, then return the value
	d = p.eval("'n' 'ame' + makeref")
	print d
	assert(d == "Jack")

	# squash
	d = p.eval("2 2 2 2 * $")
	print d
	assert(d == 16)

	# return the stack as list
	d = p.eval("(1 2 3)", None)
	print d
	assert(d == [1.0, 2.0, 3.0])

	# create a range, then return the stack as a list
	d = p.eval("10 range", None)
	print d
	assert(d == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

	# groupby (and generator) test:
	d = p.eval("(1 2 3 4 5 6 7 8) 3 {}")
	# d will be a generator, so check the contents by converting it to a list
	d = list(d)
	print d
	assert(d == [[1, 2, 3], [4, 5, 6], [7, 8]])

	# filename generation
	d = p.eval("'static' 'css' ('site-' key '.html' sum) //+")
	print d
	assert(d == "static/css/site-a7c34bd.html")

	# exception testing
	def testException(Exc, op):
		try:
			print "testing expected exception", Exc, "using code [%s]" % op
			p.eval(op)
			assert(False)
		except Exc as e:
			print "got expected exception", Exc
			pass

	# the cake is a lie
	testException(pretzyl.InvalidReference, "cake")

	# these all look like operators, but they should
	# be rejected since each one has a syntax error.
	# This results in a lookup failure (ie. KeyError in the environment)
	testException(pretzyl.InvalidReference, "2 2 *%")
	testException(pretzyl.InvalidReference, "2 2 **x")
	testException(pretzyl.InvalidReference, "2 2 ***")
	testException(pretzyl.InvalidReference, "2 2 +#")
	testException(pretzyl.InvalidReference, "2 2 $$")

	# syntax errors - mismatched brackets
	testException(pretzyl.NestingException, "( ( )")
	testException(pretzyl.NestingException, "( ( ) ) )")

	# the + operator expects two arguments, but there is only one
	testException(pretzyl.StackUnderflow, "highlander +")
	# artificially lower the stack limit, then feed the parser a large stack
	p.STACKLIMIT = 10
	testException(pretzyl.StackOverflow, "0 1 2 3 4 5 6 7 8 9 10")
	# artificially lower the stack depth, then feed the parser a deep nesting of scopes
	p.STACKDEPTH = 5
	testException(pretzyl.RecursionOverflow, "( ( ( ( ( ( ) ) ) ) ) )")
	# artificially lower the iteration limit, then feed the parser a big squash
	p.INFLIMIT = 5
	testException(pretzyl.IterationOverflow, "0 1 2 3 4 5 6 sum")

	return 0

if __name__ == "__main__":
	try:
		result = test()
	except:
		traceback.print_exc()
		pdb.post_mortem()
	sys.exit(result)
