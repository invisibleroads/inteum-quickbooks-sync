import os
import wx
import traceback
from collections import OrderedDict
from threading import Thread

from csvI import modules
from parameters import *
from quickbooks import QuickBooks
from inteumI import Inteum


welcomeText = """\
Use this program to import expenses from a spreadsheet into QuickBooks.

Make sure QuickBooks is open and that you have loaded your company file.

Choose your spreadsheet with File > Open.
"""


class MainFrame(wx.Frame):

    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title)
        self.textCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.textCtrl.SetValue(welcomeText)
        self.Show(True)
        self.CreateStatusBar()

        fileMenu = wx.Menu()
        self.fileOpen = fileMenu.Append(wx.ID_OPEN, '&Open', 'Import law firm expenses into QuickBooks')
        self.fileExit = fileMenu.Append(wx.ID_EXIT, 'E&xit', 'Terminate the program')

        menuBar = wx.MenuBar()
        menuBar.Append(fileMenu, '&File')
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.on_fileOpen, self.fileOpen)
        self.Bind(wx.EVT_MENU, self.on_fileExit, self.fileExit)

        self.Show(True)

    def on_fileOpen(self, e):
        self.folderPath = ''
        fileDialog = wx.FileDialog(self, 'Choose spreadsheet', self.folderPath, '', '*.csv', wx.OPEN)
        if fileDialog.ShowModal() == wx.ID_OK:
            self.folderPath = fileDialog.GetDirectory()
            filePath = os.path.join(self.folderPath, fileDialog.GetFilename())
            self.textCtrl.SetValue('Choose the law firm corresponding to the spreadsheet.')
            lawFirmDialog = LawFirmDialog(None, 'Choose law firm')
            if lawFirmDialog.ShowModal() == wx.ID_OK:
                self.textCtrl.Clear()
                self.fileOpen.Enable(False)
                CoreThread(
                    lawFirmDialog.selectedModule, 
                    filePath, 
                    self.textCtrl.AppendText,
                    self.on_taskEnd,
                ).start()
            else:
                self.textCtrl.SetValue(welcomeText)
            lawFirmDialog.Destroy()
        fileDialog.Destroy()

    def on_fileExit(self, e):
        self.Close(True)

    def on_taskEnd(self, isOk):
        if isOk:
            wx.MessageBox('Done.', 'Update complete')
        else:
            wx.MessageBox('Errors found', 'Update failed')
        self.fileOpen.Enable(True)


class LawFirmDialog(wx.Dialog):

    selectedModule = modules[0]

    def __init__(self, parent, title):
        wx.Dialog.__init__(self, parent, title=title)
        panel = wx.Panel(self, -1)

        x, y = 15, 15
        self.buttonRadios = []
        for moduleIndex, module in enumerate(modules):
            if moduleIndex == 0:
                options = dict(style=wx.RB_GROUP)
            y += 25
            buttonRadio = wx.RadioButton(panel, -1, module.lawFirmName.replace('&', '&&'), (x, y), **options)
            buttonRadio.Bind(wx.EVT_RADIOBUTTON, self.on_buttonRadio)
            self.buttonRadios.append(buttonRadio)

        buttonOK = wx.Button(self, wx.ID_OK, 'OK')
        buttonOK.Bind(wx.EVT_BUTTON, self.on_buttonOK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL, 'Cancel')
        buttonCancel.Bind(wx.EVT_BUTTON, self.on_buttonCancel)
        subSizer = wx.BoxSizer(wx.HORIZONTAL)
        subSizer.Add(buttonOK, 0, wx.RIGHT, 20)
        subSizer.Add(buttonCancel, 0, wx.LEFT, 20)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, wx.EXPAND)
        sizer.Add(subSizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_BOTTOM | wx.TOP | wx.BOTTOM, 10) 
        self.SetSizer(sizer)

    def on_buttonRadio(self, e):
        button = e.GetEventObject()
        self.selectedModule = modules[self.buttonRadios.index(button)]

    def on_buttonOK(self, e):
        self.EndModal(wx.ID_OK)

    def on_buttonCancel(self, e):
        self.EndModal(wx.ID_CANCEL)


class CoreThread(Thread):

    def __init__(self, module, filePath, show_text, signal_end):
        super(CoreThread, self).__init__()
        self.module = module
        self.filePath = filePath
        self.show_text = show_text
        self.signal_end = signal_end

    def summarize_candidatePacks(self, packs):
        packCount = len(packs)
        self.show_text('%i candidate%s\n' % (packCount, 's' if packCount != 1 else ''))

    def summarize_mismatches(self, mismatches):
        mismatchCount = len(mismatches)
        self.show_text('%i mismatch%s\n' % (mismatchCount, 'es' if mismatchCount != 1 else ''))

    def summarize_newPacks(self, packs):
        packCount = len(packs)
        self.show_text('%i new\n' % packCount)

    def show_error(self, error):
        self.show_text('%s\n' % error)

    def prompt_update(self, pack, oldPack):
        self.show_text('\nMismatch:\n')
        self.show_text(str(pack) + '\n')
        self.show_text(str(oldPack) + '\n')
        return True

    def prompt_save(self, newPacks, newResults):
        self.show_text('Saving...\n')
        return True

    def run(self):
        # try:
        self.show_text('Connecting to Inteum... ')
        inteum = Inteum(INTEUM_DSN)
        self.show_text('OK\n')

        self.show_text('Loading technologies... ')
        technologies = inteum.get_technologies()
        self.show_text('%s\n' % len(technologies))

        self.show_text('Loading patents... ')
        patents = inteum.get_patents()
        self.show_text('%s\n' % len(patents))

        self.show_text('Loading patentTypes... ')
        patentTypes = inteum.get_patentTypes()
        self.show_text('%s\n' % len(patentTypes))

        self.show_text('Loading lawFirms... ')
        lawFirms = inteum.get_lawFirms()
        self.show_text('%s\n' % len(lawFirms))

        self.show_text('Loading countries... ')
        countries = inteum.get_countries()
        self.show_text('%s\n' % len(countries))

        self.show_text('Loading expenses from spreadsheet... ')
        qbr = self.module(technologies, patents, patentTypes, lawFirms, countries)
        lawFirmExpenses = qbr.load_expenses(self.filePath)
        self.show_text('%s\n' % len(lawFirmExpenses))

        self.show_text('Connecting to QuickBooks... ')
        qb = QuickBooks(applicationName=QUICKBOOKS_APPLICATION_NAME)
        self.show_text('OK\n')

        self.show_text('Updating vendors in QuickBooks using lawFirms from Inteum...\n')
        qb.synchronize(lawFirms, 'Vendor', dict(
            equal=qbr.equal_lawFirm,
            parse_result=qbr.parse_vendor,
            update_result=qbr.format_vendor,
            format_result=qbr.format_vendor,
            # expand_results=
            # collapse_packs=
            prompt_update=self.prompt_update,
            prompt_save=self.prompt_save,
            show_parse_error=self.show_error,
            show_format_error=self.show_error,
            summarize_candidatePacks=self.summarize_candidatePacks,
            summarize_mismatches=self.summarize_mismatches,
            summarize_newPacks=self.summarize_newPacks,
        ))

        self.show_text('Updating customers in QuickBooks using technologies from Inteum...\n')
        qb.synchronize(technologies, 'Customer', dict(
            equal=qbr.equal_technology,
            parse_result=qbr.parse_customer,
            update_result=qbr.format_customer,
            format_result=qbr.format_customer,
            # expand_results=
            # collapse_packs=
            prompt_update=self.prompt_update,
            prompt_save=self.prompt_save,
            show_parse_error=self.show_error,
            show_format_error=self.show_error,
            summarize_candidatePacks=self.summarize_candidatePacks,
            summarize_mismatches=self.summarize_mismatches,
            summarize_newPacks=self.summarize_newPacks,
        ))

        self.show_text('Updating jobs in QuickBooks using patents from Inteum...\n')
        qb.synchronize(patents, 'Customer', dict(
            equal=qbr.equal_patent,
            parse_result=qbr.parse_job,
            update_result=qbr.format_job,
            format_result=qbr.format_job,
            # expand_results=
            # collapse_packs=
            prompt_update=self.prompt_update,
            prompt_save=self.prompt_save,
            show_parse_error=self.show_error,
            show_format_error=self.show_error,
            summarize_candidatePacks=self.summarize_candidatePacks,
            summarize_mismatches=self.summarize_mismatches,
            summarize_newPacks=self.summarize_newPacks,
        ))

        self.show_text('Updating expense accounts in QuickBooks...\n')
        qb.synchronize([{'name': '6100 - Patent Related Expenses'}], 'Account', dict(
            equal=lambda account1, account2: account1['name'].lower() == account2['name'].lower(),
            parse_result=lambda result: {'name': result['FullName']},
            # update_result=,
            format_result=lambda account, show_format_error: OrderedDict([('Name', account['name']), ('AccountType', 'Expense')]),
            # expand_results=,
            # collapse_packs=,
            # prompt_update=,
            prompt_save=self.prompt_save,
            show_parse_error=self.show_error,
            show_format_error=self.show_error,
            summarize_candidatePacks=self.summarize_candidatePacks,
            summarize_mismatches=self.summarize_mismatches,
            summarize_newPacks=self.summarize_newPacks,
        ))

        self.show_text('Updating expenses in QuickBooks using expenses from spreadsheet...\n')
        qb.synchronize(lawFirmExpenses, 'Bill', dict(
            equal=qbr.equal_expense,
            parse_result=qbr.parse_bill,
            update_result=qbr.update_bill,
            format_result=qbr.format_bill,
            expand_results=qbr.expand_bills,
            collapse_packs=qbr.collapse_expenses,
            prompt_update=self.prompt_update,
            prompt_save=self.prompt_save,
            show_parse_error=self.show_error,
            show_format_error=self.show_error,
            summarize_candidatePacks=self.summarize_candidatePacks,
            summarize_mismatches=self.summarize_mismatches,
            summarize_newPacks=self.summarize_newPacks,
        ), {'IncludeLineItems': 1})

        # except Exception, error:
            # self.show_text('\n' + traceback.format_exc() + '\n')
            # self.show_text('Failed.')
            # self.signal_end(isOk=False)
        # else:
            # self.show_text('Done.')
            # self.signal_end(isOk=True)


if __name__ == '__main__':
    app = wx.App(False)
    frame = MainFrame(None, QUICKBOOKS_APPLICATION_NAME)
    app.MainLoop()
