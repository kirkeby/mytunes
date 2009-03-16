from code import interact
import logging

log = logging.getLogger(__name__)

def run_console(context):
    while context['running']:
        try:
            source = open('repl.py').read()
            code = compile(source, 'repl.py', 'exec')
            eval(code, context)
        except:
            log.exception('Executing repl.py')
        interact(local=context)
