'Convenience classes for interacting with QuickBooks via win32com'
import datetime
from win32com.client import Dispatch, constants
from win32com.client.makepy import GenerateFromTypeLibSpec
from pythoncom import CoInitialize
from pywintypes import com_error
from collections import OrderedDict

from quickbooks.qbxml import format_request, parse_response


# After running the following command, you can check the generated type library
# for a list of dispatchable classes and their associated methods.
# The generated type library should be in site-packages/win32com/gen_py/
# e.g. /Python27/Lib/site-packages/win32com/gen_py/
GenerateFromTypeLibSpec('QBXMLRP2 1.0 Type Library')


class QuickBooks(object):
    'Wrapper for the QuickBooks RequestProcessor COM interface'

    def __init__(self, applicationID='', applicationName='Example', connectionType=constants.localQBD, companyFileName=''):
        'Connect'
        CoInitialize() # Needed in case we are running in a separate thread
        try:
            self.requestProcessor = Dispatch('QBXMLRP2.RequestProcessor.1')
        except com_error, error:
            raise QuickBooksError('Could not access QuickBooks COM interface: %s' % error)
        try:
            self.requestProcessor.OpenConnection2(applicationID, applicationName, connectionType)
            self.session = self.requestProcessor.BeginSession(companyFileName, constants.qbFileOpenDoNotCare)
        except com_error, error:
            raise QuickBooksError('Could not start QuickBooks COM interface: %s' % error)

    def __del__(self):
        'Disconnect'
        if hasattr(self, 'requestProcessor'):
            if hasattr(self, 'session'):
                self.requestProcessor.EndSession(self.session)
            self.requestProcessor.CloseConnection()

    def call(self, requestType, requestDictionary=None, qbxmlVersion='8.0', onError='stopOnError', saveXML=False):
        'Send request and parse response'
        def save_timestamp(name, content):
            now = datetime.datetime.now()
            open(now.strftime('%Y%m%d-%H%M%S') + '-%06i-%s' % (now.microsecond, name), 'wt').write(content)
        request = format_request(requestType, requestDictionary or {}, qbxmlVersion, onError)
        if saveXML:
            save_timestamp('request.xml', request)
        response = self.requestProcessor.ProcessRequest(self.session, request)
        if saveXML:
            save_timestamp('response.xml', response)
        return parse_response(response)

    def synchronize(self, candidatePacks, objectType, callbackByKey, requestDictionary=None, ignoreDuplicates=True):
        'Synchronize candidatePacks on the QuickBooks objectType using the equal comparator'
        callbackByKey.get('summarize_candidatePacks', lambda packs: None)(candidatePacks)
        # Load oldResults
        parse_result = callbackByKey.get('parse_result', lambda result: result)
        oldResults = []
        for rawResult in self.call(objectType + 'QueryRq', requestDictionary or {}):
            try:
                oldResult = parse_result(rawResult)
                oldResult[objectType] = rawResult
                oldResults.append(oldResult)
            except ParseSkip:
                pass
            except ParseError, error:
                callbackByKey.get('show_parse_error', lambda error: None)(error)
        oldPacks = callbackByKey.get('expand_results', lambda results: results)(oldResults)
        # Load newResults
        update_result = callbackByKey.get('update_result', lambda pack, show_format_error: {})
        equal = callbackByKey.get('equal', lambda pack, oldPack: True)
        newPacks = []
        mismatches = []
        for pack in candidatePacks:
            for oldPack in oldPacks:
                try:
                    if equal(pack, oldPack):
                        break
                except MismatchError:
                    mismatches.append((pack, oldPack))
                    break
            else:
                newPacks.append(pack)
        # Update mismatches
        callbackByKey.get('summarize_mismatches', lambda mismatches: None)(mismatches)
        show_format_error = callbackByKey.get('show_format_error', lambda error: None)
        for pack, oldPack in mismatches:
            if callbackByKey.get('prompt_update', lambda pack, oldPack: False)(pack, oldPack):
                modResult = update_result(pack, show_format_error)
                for key in reversed(['ListID', 'TxnID', 'EditSequence']):
                    rawResult = oldPack[objectType]
                    if rawResult.get(key):
                        modResult = OrderedDict([(key, rawResult[key])] + modResult.items())
                self.call(objectType + 'ModRq', {objectType + 'Mod': modResult})
        # Save newResults
        callbackByKey.get('summarize_newPacks', lambda packs: None)(newPacks)
        if not newPacks:
            return 0
        newResults = callbackByKey.get('collapse_packs', lambda packs: packs)(newPacks)
        if not callbackByKey.get('prompt_save', lambda newPacks, newResults: False)(newPacks, newResults):
            return
        format_result = callbackByKey.get('format_result', lambda result: result)
        for newResult in newResults:
            self.call(objectType + 'AddRq', {objectType + 'Add': format_result(newResult, show_format_error)})
        return len(newPacks)


class QuickBooksError(Exception):
    pass


class ParseSkip(Exception):
    pass


class ParseError(Exception):
    pass


class MismatchError(Exception):
    pass
