# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

# TODO: maybe move this code into the StenoDictionary itself. The current saver 
# structure is odd and awkward.
# TODO: write tests for this file

"""Common elements to all dictionary formats."""

from os.path import splitext
import shutil
import sys
import threading

# Python 2/3 compatibility.
from six import reraise

from plover.exception import DictionaryLoaderException
from plover.registry import registry
from plover.resource import ASSET_SCHEME


def _get_dictionary_module(filename):
    extension = splitext(filename)[1].lower()[1:]
    try:
        dict_module = registry.get_plugin('dictionary', extension).obj
    except KeyError:
        raise DictionaryLoaderException(
            'Unsupported extension: %s. Supported extensions: %s' %
            (extension, ', '.join(plugin.name for plugin in
                                  registry.list_plugins('dictionary'))))
    return dict_module

def create_dictionary(filename):
    '''Create a new dictionary.

    The format is inferred from the extension.

    Note: the file is not created! The resulting dictionary save
    method must be called to finalize the creation on disk.
    '''
    assert not filename.startswith(ASSET_SCHEME)
    dictionary_module = _get_dictionary_module(filename)
    if not hasattr(dictionary_module, 'create_dictionary'):
        raise DictionaryLoaderException('%s does not support creation' % dictionary_module.__name__)
    try:
        d = dictionary_module.create_dictionary()
    except Exception as e:
        ne = DictionaryLoaderException('creating %s failed: %s' % (filename, str(e)))
        reraise(type(ne), ne, sys.exc_info()[2])
    d.set_path(filename)
    d.save = ThreadedSaver(d, filename, dictionary_module.save_dictionary)
    return d

def load_dictionary(filename):
    '''Load a dictionary from a file.

    The format is inferred from the extension.
    '''
    dictionary_module = _get_dictionary_module(filename)
    try:
        d = dictionary_module.load_dictionary(filename)
    except Exception as e:
        ne = DictionaryLoaderException('loading \'%s\' failed: %s' % (filename, str(e)))
        reraise(type(ne), ne, sys.exc_info()[2])
    d.set_path(filename)
    if not filename.startswith(ASSET_SCHEME) and \
       hasattr(dictionary_module, 'save_dictionary'):
        d.save = ThreadedSaver(d, filename, dictionary_module.save_dictionary)
    return d

def save_dictionary(d, filename, saver):
    # Write the new file to a temp location.
    tmp = filename + '.tmp'
    with open(tmp, 'wb') as fp:
        saver(d, fp)

    # Then move the new file to the final location.
    shutil.move(tmp, filename)
    
class ThreadedSaver(object):
    """A callable that saves a dictionary in the background.
    
    Also makes sure that there is only one active call at a time.
    """
    def __init__(self, d, filename, saver):
        self.d = d
        self.filename = filename
        self.saver = saver
        self.lock = threading.Lock()
        
    def __call__(self):
        t = threading.Thread(target=self.save)
        t.start()
        
    def save(self):
        with self.lock:
            save_dictionary(self.d, self.filename, self.saver)
