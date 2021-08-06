#!/usr/bin/env python

"""A simple Forth-like stack based interpreter
"""

import tokenyze
import sys
import re
import os

#For internal debug use
LOG = True

def log(*args, **kwargs):
	"""For internal debug use
	"""
	if LOG:
		for arg in args:
			sys.stderr.write(str(arg))
		sys.stderr.write("\n")


#######################################################################
# Utilities


class Reference:
	"""Defines a Reference token

	Tokens can be Literals or References.
	References are names, that refer to values in an Environment.
	We encapsulate them in this class before pushing the raw names (strings) onto the stack, so that
	we can distinguish them from Literals later on.

	Literals are used as-is (ie. strings are strings, booleans are booleans, and numbers are numbers).
	"""

	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return "Reference(%s)" % str(self.name)

"""Some definitions used by the code
"""
QUOTES = "'", '"'
BOOLEANS = "True", "False"
PUSHTOKEN = "("
POPTOKEN = ")"

def convert(token):
	"""This function takes a string token and converts it into a literal or reference.

	Literals are their own values. Pretzyl uses bare None, True / False, strings and numbers to represent these values.

	Tokens that cannot be converted as one of these, is encapsulated in a Reference instance,
	so that the rest of Pretzyl will know that these should refer to named values in the environment.
	"""
	if token == "None":
		return None
	if token in BOOLEANS:
		return bool(token)
	try:
		if re.match(r"^-?0\d+$", token):
			number = int(token[1:], 8) # octal
		elif re.match(r"^-?0[xX][\da-fA-F]+$", token):
			number = int(token[2:], 16) # hex
		elif re.match(r"^-?\d+$", token):
			number = int(token) # base-10
		else:
			number = float(token)
		return number
	except ValueError:
		pass
	if len(token) > 1:
		quotes = token[0], token[-1]
		if quotes[0] == quotes[1] and quotes[0] in QUOTES:
			# must be a string
			return token[1:-1]
	# must be a reference
	return Reference(token)

def tokenize(line, macros = None):
	"""This method attempts tokenize and translate an input line of program code.

	If macros is a dictionary of translations, it is applied after the initial
	tokenization to expand any macros in the line.
	
	The result will be a list of literals / references.
	"""
	if macros is None:
		# no macro lookup, just convert each token in the line
		return [convert(token) for token in tokenyze.gettokens(line)]
	# do macro expansion
	tokenlist = []
	for token in tokenyze.gettokens(line):
		if token in macros:
			# if the token is a macro, tokenize its macro expansion and convert each resulting token
			tokenlist.extend([convert(token) for token in tokenyze.gettokens(macros[token])])
		else:
			# convert the non-macro token
			tokenlist.append(convert(token))
	return tokenlist


#######################################################################
# Default operators

import functools
import math

class Operator:
	"""User-derived classes that want to implement operators should derive from this base class.

	Operator classes should implement
		def __call__(self, P)
	which takes a Pretzyl parser as argument when called during program execution.
	An operator class should be registered in the environment passed to the parser, in order to be available
	when a program invokes it using its reference name.
	"""
	def __init__(self):
		pass

class makeBareOperator:
	"""A decorator that creates a bare operator from a function that accepts a Pretzyl parser during invocation.
	The decorator handles popping of tokens off the stack, as well as lookup.
	The bare operator needs to all other interaction with the stack, including pushing values if required.

	"""

	def __init__(self, argc = 1, lookup = False):
		self.lookup = lookup
		self.argc = argc

	def __call__(self, function):
		@functools.wraps(function)
		def wrapper(P):
			log("makeBareOperator: popping %i args from stack depth %i" % (self.argc, P.depth()))
			argv = P.pop(self.argc, self.lookup)
			#try:
			if 1:
				if self.argc == 0:
					out = function(P)
				elif self.argc == 1:
					out = function(P, argv)
				else:
					out = function(P, *argv)
			#except IterationOverflow as e:
			#	raise
			# The following will squash everything into an ExecutionError...
			#except Exception as e:
			#	raise ExecutionException(e, "\n\terror applying operator [%s]" % function), None, sys.exc_info()[2]
		# the 'pretzyloperator' attribute allows Pretzyl to determine that this object is a valid pretzyl operator
		wrapper.pretzyloperator = True
		return wrapper

class makeOperator:
	"""A decorator that creates a simple operator that is provided its arguments from the stack.
	The return value is pushed back onto the stack
	By default, all requested arguments are looked up in the environment.

	"""

	def __init__(self, argc = 1, lookup = True):
		self.lookup = lookup
		self.argc = argc

	def __call__(self, function):
		@functools.wraps(function)
		def wrapper(P):
			log("makeOperator: popping %i args from stack depth %i" % (self.argc, P.depth()))
			argv = P.pop(self.argc, self.lookup)
			#try:
			if 1:
				if self.argc == 0:
					out = function()
				elif self.argc == 1:
					out = function(argv)
				else:
					out = function(*argv)
			#except IterationOverflow as e:
			#	raise
			# The following will squash everything into an ExecutionError...
			#except Exception as e:
			#	raise ExecutionException(e, "\n\terror applying operator [%s]" % function), None, sys.exc_info()[2]
			P.push(out)
		# the 'pretzyloperator' attribute allows Pretzyl to determine that this object is a valid pretzyl operator
		wrapper.pretzyloperator = True
		return wrapper


# The following declares a number of operators that are available by default in Pretyl.
# Most of them are self-explanatory.

# Note that some operators will push something other than a number, string or boolean onto the stack.
# In fact, almost any python structure is acceptable, if the next operator that comes along can operate on it.
# 
# Sometimes we will get a "TypeError: object of type 'generator' has no len()" exception when 
# applying eg. a "length" operator to an object. This might be because the object in question
# was made with "groupby" or "enumerate", which produce generators (which have no __len__).
# Since we don't have Exception Chaining in Python 2.7 it is pretty hard to catch these 
# errors at their source. Ergo, this note. Hope it helps...


@makeBareOperator(1)
def isset(P, a):
	"""Checks whether a token is a valid reference to an object in the environment.
	"""
	P.push(P.validref(a))

@makeOperator(2)
def greaterthan(a, b):
	return a > b

@makeOperator(2)
def lessthan(a, b):
	return a < b

@makeOperator(2)
def contains(a, b):
	return a is not None and b in a

@makeOperator(2)
def equals(a, b):
	return a == b

@makeOperator(2)
def greaterequal(a, b):
	return a >= b

@makeOperator(1)
def invert(a):
	return not a

@makeBareOperator(2)
def and_(P, a, b):
	"""Short-circuit 'and' operator.
	The second argument is not looked up if the first argument evaluates to False
	"""
	P.push(P.lookup(b) if P.lookup(a) else False)

@makeBareOperator(2)
def or_(P, a, b):
	"""Short-circuit 'or' operator.
	The second argument is not looked up if the first argument evaluates to True
	"""
	P.push(P.lookup(b) if not P.lookup(a) else True)

@makeOperator(2)
def strftime(date, format):
	return date.strftime(format)

@makeOperator(2)
def truncate(text, words):
	"""Truncates a piece of html text at the required number of words
	"""
	return ' '.join(re.sub('(?s)<.*?>', ' ', text).split()[:words])

@makeOperator(2)
def pathjoin(a, b):
	return os.path.join(a, b)
	#return b if len(a) == 0 else a + "/" + b

@makeOperator(1)
def toreference(literal):
	"""Uses a string to create a reference.
	This is useful when the name of a reference needs to be constructed at runtime
	"""
	return Reference(literal)

@makeOperator(2)
def multiply(a, b):
	return a * b

@makeOperator(2)
def add(a, b):
	return a + b

@makeOperator(2)
def subtract(a, b):
	return a - b

@makeOperator(2)
def divide(a, b):
	"""Floating point division.
	The result should be converted to an integer if required
	"""
	return float(a) / b

@makeOperator(1)
def ceil(a):
	return math.ceil(a)

@makeOperator(1)
def floor(a):
	return math.floor(a)

@makeOperator(1)
def range_(count):
	"""Returns range(count).
	Note: range is a generator, so using something like "length" on the result of this operator
	will fail hard
	"""
	return range(int(count))

@makeOperator(1)
def int_(a):
	return int(a)

@makeOperator(1)
def str_(a):
	return str(a)

@makeOperator(1)
def enumerate_(list):
	"""Returns enumerate(list).
	Note: enumerate is a generator, so using something like "length" on the result of this operator
	will fail hard
	"""
	return enumerate(list)

@makeOperator(1)
def length_(a):
	return len(a)

@makeOperator(2)
def at_(a, index):
	return a[index]

@makeOperator(3)
def slice_(a, start, end):
	if start is None:
		return a[:end]
	if end is None:
		return a[start:]
	return a[start:end]

@makeOperator(2)
def groupby(a, groupsize):
	"""Breaks a list of items into groups of groupsize.
	The last group will contain the remaainder.
	For example "(1 2 3 4 5 6 7 8) 3 groupby"
	will return [[1, 2, 3], [4, 5, 6], [7, 8]]
	Note: this returns a generator, so using something like "length" on the result of this operator
	will fail hard.
	"""
	return (a[i:i + groupsize] for i in range(0, len(a), groupsize))

@makeOperator(3)
def choose(first, second, predicate):
	"""Chooses between first and second based on the boolean value of third
	ie. third ? first : second
	"""
	return first if predicate else second

@makeOperator(2)
def startswith(value, start):
	return value.startswith(start)

@makeOperator(2)
def endswith(value, end):
	return value.endswith(end)

@makeOperator(2)
def paths(a, depth):
	return a.paths(depth)

@makeOperator(1)
def iteritems(a):
	"""Note: returns a generator. Applying "length" to this object will result in a hard fail
	"""
	return a.iteritems()

@makeBareOperator(0)
def dup(P):
	"""Duplicates the top token on the stack without looking up its value
	"""
	P.push(P.peek())

@makeOperator(2)
def pow_(a, b):
	return a ** b

## The following are Modifiers

@makeBareOperator(0)
def squash(P):
	"""Squash will repeat the last operator until there are not enough items on the stack.
	The upper limit of execution is INFLIMIT.
	"""
	try:
		for i in range(P.INFLIMIT):
			log("squash: running op", P.lastop, "on stacksize:", len(P.stacks[-1]))
			P.lastop(P)
		else:
			raise IterationOverflow("iteration overflow on loop %i using operator squash on [%s]" % (i, P.lastop))
	except StackUnderflow as e:
		pass

@makeBareOperator(1)
def times(P, a):
	"""Times will repeat the last operator N-1 number of times, so that the last operator
	gets repeated N times in total.
	It fails if we run out of stack space or exceed the iteration limit.
	"""
	assert(a > 0)
	if a > P.INFLIMIT:
		raise IterationOverflow("iteration overflow using operator times(%i) on [%s]" % (a, P.lastop))
	for i in range(a - 1): # since we are repeating an operation, we have already done this once
		P.lastop(P)

# A handy dictionary of the default operators.

DefaultOperators = {
	'exists'		: isset,
	'gt'			: greaterthan,
	'lt'			: lessthan,
	'contains' 		: contains,
	'eq' 			: equals,
	'ge'			: greaterequal,
	'not' 			: invert,
	'and' 			: and_,
	'or' 			: or_,
	'strftime'  	: strftime,
	'truncate'		: truncate,
	'pathjoin' 		: pathjoin,
	'makeref' 		: toreference,
	'mul' 			: multiply,
	'add' 			: add,
	'subtract' 		: subtract,
	'div' 			: divide,
	'ceil' 			: ceil,
	'floor'			: floor,
	'range' 		: range_,
	'int' 			: int_,
	'str' 			: str_,
	'enumerate' 	: enumerate_,
	'length' 		: length_,
	'at' 			: at_,
	'slice' 		: slice_,
	'groupby' 		: groupby,
	'choose' 		: choose,
	'startswith' 	: startswith,
	'endswith' 		: endswith,
	'paths' 		: paths,
	'iteritems' 	: iteritems,
	'dup'			: dup,
	'pow' 			: pow_,
	# modifiers of the last operator
	'squash'		: squash,
	'times'			: times,
}

# A handy dictionary of macro symbols.

MacroSymbols = {
	'>': 	'gt',
	'<':	'lt',
	'==':	'eq',
	'>=':	'ge',
	'!':	'not',
	'&': 	'and',
	'|': 	'or',
	'~': 	'makeref',
	'*': 	'mul',
	'+': 	'add',
	'-': 	'sub',
	'/': 	'div',
	'^': 	'ceil',
	'_': 	'floor',
	'<>': 	'at',
	'||': 	'length',
	'[]': 	'slice',
	'{}': 	'groupby',
	'?': 	'choose',
	'?]': 	'startswith',
	'[?': 	'endswith',
	'//': 	'paths',
	'@': 	'iteritems',
	'$': 	'squash',
	'sum': 	'add squash',
	'prod': 'mul squash',
	'any': 	'or squash',
	'all': 	'and squash',
	'//+': 	'pathjoin squash',
	'/+': 	'pathjoin',
	'**': 	'pow',
	'*2': 	'2 pow',
}

###############################################################################
# The Pretzyl class


class Pretzyl:
	"""This is the core interpreter of Pretzyl

	It defines both the external API for a user to process a program with,a
	as well as the operator API with which operators (both default and custom)
	can interact with the stack.

	It processes a text program into tokens, evaluates each token in turn,
	and arranges the output on a heap of stacks. It also holds the environment,
	with which operators can interact using the stack.
	"""

	STACKLIMIT = 256
	STACKDEPTH = 10
	INFLIMIT = 256 # set to float('Inf') for no limit

	def __init__(self, environment = {}, operators = DefaultOperators, operatorpath = None, macros = MacroSymbols):
		self.env = environment
		self.operatorpath = operatorpath
		self.macros = macros if macros is not None else {}
		self.operatorpath = operatorpath
		if operatorpath is None:
			self.env.update(operators)
		else:
			# this assumes that self.env has an update that takes a path
			self.env.update(operators, self.operatorpath)

	def getopenv(self):
		"""Returns the part of the environment where operators can be found
		"""
		if self.operatorpath is None:
			return self.env
		else:
			return self.env[self.operatorpath]

	def validref(self, token):
		"""Checks whether a token is a valid reference in the environment
		"""
		return isinstance(token, Reference) and token.name in self.env

	def lookup(self, token):
		"""Resolves the value of a token.
		Reference tokens refer to objects in the environment. If a reference refers
		to a non-existent object, an InvalidReference exception is raised.
		Literal tokens are their own value.
		"""
		if isinstance(token, Reference):
			try:
				return self.env[token.name]
			except KeyError as e:
				raise InvalidReference("token with name [%s] not found" % token.name)
		return token

	def checkstack(self, minsize):
		"""Checks whether the stack has (at least) the required minsize length
		"""
		if self.depth() < minsize:
			raise StackUnderflow("stack depth %i is shallower than required %i" % (self.depth(), minsize))

	def peek(self, count = 1, lookup = True):
		"""Returns the specified number of tokens from the top of the stack, without popping them.
		If lookup is specified, reference tokens are resolved in the environment and their objects returned.
		"""
		self.checkstack(count)
		items = self.stacks[-1][-count:]
		if lookup:
			items = [self.lookup(item) for item in items]
		return items[0] if len(items) == 1 else items if len(items) > 1 else None

	def pop(self, count = 1, lookup = True):
		"""Returns the top count tokens in the stack
		The tokens are removed from the stack.
		They are returned in FIFO order, and if lookup is True,
		their values in the environment are looked up. 
		"""
		if count is None:
			# return eveything:
			self.stacks[-1], items = [], self.stacks[-1]
		else:
			self.checkstack(count)
			if count > 0:
				# chop the last count items off the stack
				self.stacks[-1], items = self.stacks[-1][:-count], self.stacks[-1][-count:]
				assert(len(items) == count)
			else:
				# nothing to do, return None
				return None
				# remove all items from the stack
				#self.stacks[-1], items = [], self.stacks[-1]
			assert(len(items) == count)
		# do lookup, if required
		if lookup:
			items = [self.lookup(item) for item in items]
		# return 1, all or none
		return items[0] if len(items) == 1 else items if len(items) > 1 else None

	def push(self, value):
		"""Pushes a token onto the topmost stack
		"""
		if self.depth() + 1 > self.STACKLIMIT:
			raise StackOverflow("stack overflow, stack depth %i exceeds STACKLIMIT %i" % (self.depth(), self.STACKLIMIT))
		self.stacks[-1].append(value)

	def depth(self):
		"""Retuens the depth of the topmost stack
		"""
		return len(self.stacks[-1])

	def pushstack(self):
		"""Adds a stack to the heap of stacks
		The stack becomes the new active top stack.
		This is done when an opening bracket token is found.
		"""
		if len(self.stacks) + 1 > self.STACKDEPTH:
			raise RecursionOverflow("recursion overflow, stacks size %i exceeds STACKDEPTH %i" % (len(self.stacks), self.STACKDEPTH))
		self.stacks.append([])

	def popstack(self):
		"""Pops the top stack from the heap of stacks
		The contents of the stack is added to the new top stack.
		This is done when an closing bracket token is found.
		"""
		if len(self.stacks) == 1:
			raise NestingException("cannot pop last stack")
		laststack = self.stacks.pop()
		if len(laststack) == 1:
			self.push(laststack[0])
		elif len(laststack) > 1:
			self.push(laststack)
		else:
			pass

	def makeoperator(self, token):
		"""This method attempts to make an operator (possibly with modifier) out of a token
		If succesful, the operator(+modifier) is executed, and the method returns True.
		Otherwise, the method returns False.
		"""
		log("makeoperator[%s]:" % token)
		if not isinstance(token, Reference):
			# simply return false, this is not a reference
			log("-> not a reference")
			return False
		openv = self.getopenv()
		if token.name in openv:
			obj = openv[token.name]
		else:
			return False
		try:
			if isinstance(obj, Operator):
				log("-> found Operator")
			elif 'pretzyloperator' in obj.__dict__ and obj.__dict__['pretzyloperator']:
				log("-> found wrapped operator function")
			else:
				log("-> not an Operator or wrapped operator function")
				return False
		except AttributeError as e:
			log("-> error accessing attributes, discarding operator")
			return False
		# At this point, the object should be an operator.
		operator = obj
		log("running operator [%s], last operator is [%s]" % (operator, self.lastop))
		# pass our environment to the operator for evaluation.
		operator(self)
		self.lastop = operator
		return True

	def eval(self, line, count = 1, lookup = True):
		"""This method evaluates a complete program.
		It returns the count number of items from the bottom level stack, and looks
		up their values in the environment if requested.
		"""
		# each evaluation starts off with a new stack
		self.stacks = [[]]
		self.lastop = None
		log("line is [%s]" % line)
		# do macro symbol translation and tokenize the line:
		tokens = tokenize(line, self.macros)
		log("tokens are ", tokens)
		tokens.reverse()
		# evaluate one token at a time.
		while len(tokens) > 0:
			token = tokens.pop()
			log("looking at token [%s], stack depth: %i" % (token, self.depth()))
			if isinstance(token, Reference):
				if token.name == PUSHTOKEN:
					log("-> token is PUSHTOKEN")
					# push a new input stack on top of the old stack
					self.pushstack()
					continue
				elif token.name == POPTOKEN:
					log("-> token is POPTOKEN")
					# pop the current stack, add its value to the next stack
					self.popstack()
					continue
				else:
					if self.makeoperator(token):
						continue
			# otherwise push it onto the stack
			log("-> token [%s] is a literal, adding to stack" % token)
			self.push(token)
		# we need to make sure our stackdepth is 1
		if len(self.stacks) != 1:
			# probably a syntax error: no matching closing bracket.
			raise NestingException("syntax error, missing closing bracket(s) for [%s]" % line)
		return self.pop(count, lookup)


#######################################################################
### Exceptions

class BaseException(Exception):
	"""Base exception class for this module
	"""
	def __init__(self, message):
		Exception.__init__(self)

class RecursionOverflow(BaseException):
	"""Recursion overflow

	This exception is raised when the stack depth exceeds the STACKDEPTH limit, ie. there 
	are too may heirarchical open brackets in the program
	"""
	def __init__(self, message):
		BaseException.__init__(self, message)

class NestingException(BaseException):
	"""Nesting exception

	This is raised when there are mismatched brackets in the program. Either one too many
	closing brackets, or too few closing brackets.
	In either case, the number and nesting of brackets do not match.
	This is a syntax error in the program.
	"""
	def __init__(self, message):
		BaseException.__init__(self, message)

class StackUnderflow(BaseException):
	"""Stack underflow

	Raised by the interpreter when an operation attempts to pop more values
	off the stack than are currently available.
	"""
	def __init__(self, message):
		BaseException.__init__(self, message)

class StackOverflow(BaseException):
	"""Stack overflow

	Raised by the interpreter when an operation attempts to push more values
	onto the stack than are currently allowed.
	"""
	def __init__(self, message):
		BaseException.__init__(self, message)

class IterationOverflow(BaseException):
	"""Iteration overflow

	Raised by the interpreter when a modified inf repeat operation does not terminate
	before the expected number of iterations.
	"""
	def __init__(self, message):
		BaseException.__init__(self, message)

class InvalidReference(BaseException):
	"""Invalid reference token lookup
	"""
	def __init__(self, message):
		BaseException.__init__(self, message)

class MalformedOperator(BaseException):
	"""Operator syntax error

	This is an internal exception that is used during operator parsing, to indicate
	that the operator (specifically, its modifier) is malformed, and that the 
	operator should be treated as a regular reference instead.
	"""
	def __init__(self, message):
		BaseException.__init__(self, message)

class ExecutionException(BaseException):
	def __init__(self, exception, message):
		message = repr(exception) + message
		BaseException.__init__(self, message)

