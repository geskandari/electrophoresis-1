import sys
import psycopg2
import tkinter as tk
from tkintertable import TableCanvas, TableModel
from tkinter import messagebox
import calendar
import datetime
import DatabaseCredentials

class Calendar:
    def __init__(self, parent, gui):
        self.gui = gui
        self.values = {}
        self.parent = parent
        self.cal = calendar.TextCalendar(calendar.SUNDAY)
        self.year = datetime.date.today().year
        self.month = datetime.date.today().month
        self.wid = []
        self.day_selected = 1
        self.month_selected = self.month
        self.year_selected = self.year
        self.day_name = ''

        self.setup(self.year, self.month)

    def clear(self):
        for w in self.wid[:]:
            w.grid_forget()
            self.wid.remove(w)

    def go_prev(self):
        if self.month > 1:
            self.month -= 1
        else:
            self.month = 12
            self.year -= 1

        self.clear()
        self.setup(self.year, self.month)

    def go_next(self):
        if self.month < 12:
            self.month += 1
        else:
            self.month = 1
            self.year += 1

        self.clear()
        self.setup(self.year, self.month)

    def selection(self, day, name):
        self.day_selected = day
        self.month_selected = self.month
        self.year_selected = self.year
        self.day_name = name

        # data
        self.values['day_selected'] = day
        self.values['month_selected'] = self.month
        self.values['year_selected'] = self.year
        self.values['day_name'] = name
        self.values['month_name'] = calendar.month_name[self.month_selected]

        self.clear()
        self.setup(self.year, self.month)

    def setup(self, y, m):
        left = tk.Button(self.parent, text='<', command=self.go_prev)
        self.wid.append(left)
        left.grid(row=0, column=1)

        header = tk.Label(self.parent, height=2, text='{}   {}'.format(calendar.month_abbr[m], str(y)))
        self.wid.append(header)
        header.grid(row=0, column=2, columnspan=3)

        right = tk.Button(self.parent, text='>', command=self.go_next)
        self.wid.append(right)
        right.grid(row=0, column=5)

        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        for num, name in enumerate(days):
            t = tk.Label(self.parent, text=name[:3])
            self.wid.append(t)
            t.grid(row=1, column=num)

        for w, week in enumerate(self.cal.monthdayscalendar(y, m), 2):
            for d, day in enumerate(week):
                if day:
                    b = tk.Button(self.parent, width=1, text=day,
                                  command=lambda day=day: self.selection(day, calendar.day_name[(day - 1) % 7]))
                    self.wid.append(b)
                    b.grid(row=w, column=d)

        sel = tk.Label(self.parent, height=2,
                       text='{} {} {}'.format(calendar.month_name[self.month_selected], self.day_selected,
                                              self.year_selected))
        self.wid.append(sel)
        sel.grid(row=8, column=0, columnspan=7)

        ok = tk.Button(self.parent, width=5, text='OK', command=self.kill_and_save)
        self.wid.append(ok)
        ok.grid(row=9, column=2, columnspan=3, pady=10)

    def kill_and_save(self):
        date_object = datetime.date(self.year_selected, self.month_selected, self.day_selected)
        self.gui.update_date(date_object)
        self.parent.destroy()


class DatabaseConnection:

    def __init__(self):
        self.connection = psycopg2.connect(
            host=DatabaseCredentials.DB_hostname,
            dbname=DatabaseCredentials.DB_name,
            port="5432",
            user=DatabaseCredentials.DB_username,
            password=DatabaseCredentials.DB_password)

    def close_database_connection(self):
        self.connection.close()

    def get_rows_for_date(self, dateObject):
        cur = self.connection.cursor()
        cur.execute("""select data_analisi, data_prel, seq, programma, eta, pt,
            nome_1, fraz_1, nome_2, fraz_2, nome_3, fraz_3, nome_4, fraz_4, nome_5, fraz_5, free1, nominativo
            from anagrafica where programma = 'S' AND data_analisi = (%s) order by seq asc""", [dateObject])
        databaseRows = cur.fetchall()
        cur.close()

        rows = []
        for databaseRow in databaseRows:
            newDataRow = RowData(databaseRow)
            rows.append(newDataRow)

        return rows

    def get_history(self, mrn):
        cur_history = self.connection.cursor()
        cur_history.execute("""select data_analisi, data_prel, seq, programma, commento1, pt * val_picco_1 / 100 as val_picco_1, free3, free5, longmemo, free1, seq
                    from anagrafica
                    
                    where programma != 'T' and
                    free1 = (%s) and
                    data_analisi is not null
                    
                    order by data_analisi desc""", [mrn])
        ### not hemoglobin, mrn matches, and is verified

        prev_history = cur_history.fetchall()
        prev_history_list = []
        for databaseRow in prev_history:
            ph = PreviousHistory(databaseRow)
            prev_history_list.append(ph)

        cur_history.close()
        return prev_history_list

class PreviousHistory:
    def __init__(self, database_row):
        self.verified_time = database_row[0]
        self.collect_time = database_row[1]
        self.program = database_row[3]
        self.ordering_provider = database_row[6]

        if database_row[5] is None:
            self.band_concentration = 0
        else:
            self.band_concentration = round(database_row[5], 2)

        self.signout_pathologist = database_row[4]
        self.interpretation = database_row[8]

    def get_formatted_verified_time(self):
        if self.verified_time is None:
            return ''
        return self.verified_time.strftime("%Y-%m-%d")

    def get_program_description(self):
        switcher = {
            'S' : 'SPEP',
            'J': 'CSPE',
            'A': 'OCBE',
            '6': 'UPEP',
        }
        return switcher.get(self.program, "Invalid Program" + self.program)

class GUI:
    def __init__(self, database_connection):
        self.database_connection = database_connection
        self.rowNumber = -1
        self.rows = {}
        self.X = ""
        self.H = 'No'
        self.B = 'No'

        self.root = tk.Tk()
        self.root.title('')
        canvas = tk.Canvas(self.root, height=600, width=1500)
        canvas.pack()
        self.frame = tk.Frame(self.root)
        self.frame.place(relx=0, rely=0, relwidth=0.5, relheight=1)
        self.tframe = tk.Frame(self.root)
        self.tframe.place(relx=0.5, rely=0.0, relwidth=0.5, relheight=0.5)

        # table build
        self.table = TableCanvas(self.tframe, rows=2, cols=4, cellwidth=175, state="readonly")
        self.table_value = TableCanvas(self.frame, rows=2, cols=6, cellwidth=117, state="readonly")
        self.table_value.show()

        self.table.bind('<ButtonRelease-1>', self.clicked)  # Bind the click release event

        self.table.model.columnlabels['1'] = "VerifiedDate"
        self.table.model.columnlabels['2'] = "Program"
        self.table.model.columnlabels['3'] = "OrdPhysician"
        self.table.model.columnlabels['4'] = "BandQ"
        self.table.show()

        self.table_value.model.columnlabels['1'] = "Total Protein"
        self.table_value.model.columnlabels['2'] = "Albumin"
        self.table_value.model.columnlabels['3'] = "Alpha1"
        self.table_value.model.columnlabels['4'] = "Alpha2"
        self.table_value.model.columnlabels['5'] = "Beta"
        self.table_value.model.columnlabels['6'] = "Gamma"

        self.hframe = tk.Frame(self.root)
        self.hframe.place(relx=0.5, rely=0.5, relwidth=0.5, relheight=0.57)
        self.History = tk.Label(self.frame, text='Does this patient have a previous history?', font=15)
        self.History.place(relx=0.13, rely=0.22, relwidth=0.8, relheight=0.1)
        self.var1 = tk.IntVar()
        self.var1.set('no')
        self.button_Y_H = tk.Radiobutton(self.frame, text="Yes", font=8, variable=self.var1, value='yes',
                                         command=self.HY)
        self.button_N_H = tk.Radiobutton(self.frame, text="No", font=8, variable=self.var1, value='no', command=self.HN)
        self.button_Y_H.place(relx=0.35, rely=0.35, relwidth=0.10, relheight=0.05)
        self.button_N_H.place(relx=0.55, rely=0.35, relwidth=0.10, relheight=0.05)
        self.Band = tk.Label(self.frame, text='Is there a band present in the current study?', font=15)
        self.Band.place(relx=0.13, rely=0.42, relwidth=0.8, relheight=0.1)
        self.var2 = tk.IntVar()
        self.var2.set('no')
        self.button_Y_B = tk.Radiobutton(self.frame, text="Yes", font=8, variable=self.var2, value='yes',
                                         command=self.BY)
        self.button_N_B = tk.Radiobutton(self.frame, text="No", font=8, variable=self.var2, value='no', command=self.BN)
        self.button_Y_B.place(relx=0.35, rely=0.53, relwidth=0.10, relheight=0.05)
        self.button_N_B.place(relx=0.55, rely=0.53, relwidth=0.10, relheight=0.05)
        self.comment = tk.Text(self.frame, height=30, width=10)
        self.comment.place(relx=0.13, rely=0.60, relwidth=0.8, relheight=0.35)
        self.button_next = tk.Button(self.frame, text="Next", font=8, command=self.next_row)
        self.button_next.place(relx=0.9, rely=0.22, relwidth=0.1, relheight=0.1)
        self.button_prev = tk.Button(self.frame, text="Previous", font=8, command=self.prev_row)
        self.button_prev.place(relx=0.06, rely=0.22, relwidth=0.1, relheight=0.1)
        self.button_close = tk.Button(self.frame, text="Close", font=8, command=self.close)
        self.button_close.place(relx=0.473, rely=0.95, relwidth=0.07, relheight=0.05)
        self.button_pickday = tk.Button(self.frame, text="Pick Day", font=8, command=self.pickDate)
        self.button_pickday.place(relx=0.4, rely=0.15, relwidth=0.1, relheight=0.05)
        self.history_comment = tk.Text(self.hframe, height=30, width=10)
        self.history_comment.place(relx=0.1, rely=0.1, relwidth=0.8, relheight=0.6)

        self.attending = tk.Label(self.hframe, text='', font=15)
        self.attending.place(relx=0.125, rely=0.75, relwidth=0.8, relheight=0.1)

        self.date_label = tk.Label(self.frame, text='', font=15)
        self.date_label.place(relx=0.5, rely=0.15, relwidth=0.16, relheight=0.05)

        # TODO default date to today's date
        default_date = '09-08-2016'
        self.update_date(default_date)

    def update_date(self, new_date):
        self.rows = database_connection.get_rows_for_date(new_date)
        self.date_label.config(text=new_date)
        self.rowNumber = 0
        self.resetTK()

    def close(self):
        self.root.destroy()

    def next_row(self):
        if self.rowNumber == len(self.rows) - 1:
            return
        self.rowNumber = self.rowNumber + 1
        self.thisRowData = self.rows[self.rowNumber]
        self.var1.set('no')
        self.var2.set('no')
        self.H = 'No'
        self.B = 'No'
        self.updateTK()

    def prev_row(self):
        if self.rowNumber == 0:
            return
        self.rowNumber = self.rowNumber - 1
        self.thisRowData = self.rows[self.rowNumber]
        self.var1.set('no')
        self.var2.set('no')
        self.H = 'No'
        self.B = 'No'
        self.updateTK()

    def resetTK(self):
        self.rowNumber = -1
        self.thisRowData = None
        self.next_row()
        self.updateTK()

    def pickDate(self):
        calendarPopupFrame = tk.Toplevel()
        calendarObject = Calendar(calendarPopupFrame, self)

    def HY(self):
        self.H = 'Yes'
        self.updateTK()

    def HN(self):
        self.H = 'No'
        self.updateTK()

    def BY(self):
        self.B = 'Yes'
        self.updateTK()

    def BN(self):
        self.B = 'No'
        self.updateTK()

    def clicked(self, event):  # Click event callback function.
        self.updateHistoryComment()

    def updateHistoryComment(self):
        currentPatientHistoryRecord = self.getCurrentPatientHistoryRecord()
        if currentPatientHistoryRecord is None:
            return

        self.attending.config(text=currentPatientHistoryRecord.signout_pathologist)
        self.history_comment.delete('1.0', tk.END)
        self.history_comment.insert(tk.END, str(currentPatientHistoryRecord.interpretation))
        self.table.redrawTable()

    def getCurrentPatientHistoryRecord(self):
        currentTableRecord = self.table.get_currentRecord()
        for ph in self.patient_history:
            if currentTableRecord['1'] == ph.get_formatted_verified_time() and \
                    currentTableRecord['2'] == ph.get_program_description() and \
                    currentTableRecord['3'] == ph.ordering_provider and \
                    currentTableRecord['4'] == ph.band_concentration:
                return ph
        return None

    def updateTK(self):
        # update button text
        self.History.config(text='Case ' + str(
            self.thisRowData.seq) + ': Does ' + self.thisRowData.patientName + ' have a previous history?')

        # update history comment and attending
        self.attending.config(text='')
        self.history_comment.delete('1.0', tk.END)
        self.history_comment.insert(tk.END, str(''))

        self.table_value.model.setValueAt(self.thisRowData.pt, 0, 0)
        self.table_value.model.setValueAt(self.thisRowData.getAbsAlbuminText(), 0, 1)
        self.table_value.model.setValueAt(self.thisRowData.getAbsAlpha1Text(), 0, 2)
        self.table_value.model.setValueAt(self.thisRowData.getAbsAlpha2Text(), 0, 3)
        self.table_value.model.setValueAt(self.thisRowData.getAbsBetaText(), 0, 4)
        self.table_value.model.setValueAt(self.thisRowData.getAbsGammaText(), 0, 5)

        self.table_value.model.setValueAt(str(self.thisRowData.getRelAlbuminText()), 1, 1)
        self.table_value.model.setValueAt(str(self.thisRowData.getRelAlpha1Text()), 1, 2)
        self.table_value.model.setValueAt(str(self.thisRowData.getRelAlpha2Text()), 1, 3)
        self.table_value.model.setValueAt(str(self.thisRowData.getRelBetaText()), 1, 4)
        self.table_value.model.setValueAt(str(self.thisRowData.getRelGammaText()), 1, 5)

        self.table_value.redrawTable()
        # update suggested comment
        new_comment = ""
        try:
            new_comment = CommentInterpreter.CM(self.thisRowData, self.H, self.B)
        except:
            new_comment = "An error occurred when trying to create the comment"
        self.comment.delete('1.0', tk.END)
        self.comment.insert(tk.END, str(new_comment))

        # update historical table
        self.table.model.deleteRows()
        self.table.clearSelected()
        self.table.redrawTable()

        if self.thisRowData.mrn is None:
            return

        self.patient_history = database_connection.get_history(str(self.thisRowData.mrn))

        # add a row for each new history element
        for ph in self.patient_history:
            new_row_index = self.table.model.addRow() - 1
            self.table.model.setValueAt(ph.verified_time.strftime("%Y-%m-%d"), new_row_index, 0)
            self.table.model.setValueAt(ph.get_program_description(), new_row_index, 1)
            self.table.model.setValueAt(ph.ordering_provider, new_row_index, 2)
            self.table.model.setValueAt(ph.band_concentration, new_row_index, 3)

        self.table.setSelectedRow(0)
        self.updateHistoryComment()


    def mainloop(self):
        self.root.mainloop()


class RowData:
    albuminRLow = 55.8
    albuminRHigh = 66.1
    albuminALow = 3.51
    albuminAHigh = 5.42

    alpha1RLow = 2.9
    alpha1RHigh = 4.9
    alpha1ALow = .18
    alpha1AHigh = .4

    alpha2RLow = 7.1
    alpha2RHigh = 11.8
    alpha2ALow = .44
    alpha2AHigh = .96

    betaRLow = 8.4
    betaRHigh = 13.1
    betaALow = .52
    betaAHigh = 1.07

    gammaRLow = 11.1
    gammaRHigh = 18.8
    gammaALow = .7
    gammaAHigh = 1.54

    proteinALow = 6.3

    def __init__(self, row):
        data_analisi = row[0]
        data_prel = row[1]
        self.seq = row[2]
        programma = row[3]

        nome_1 = row[6]
        nome_2 = row[8]
        nome_3 = row[10]
        nome_4 = row[12]
        nome_5 = row[14]

        self.eta = row[4]
        self.pt = row[5]
        self.patientRelAlbumin = row[7]
        self.patientRelAlpha1 = row[9]
        self.patientRelAlpha2 = row[11]
        self.patientRelBeta = row[13]
        self.patientRelGamma = row[15]
        self.mrn = row[16]
        self.patientName = row[17]

        # TODO remove me
        self.pt = 6.3
        self.eta = 64

        self.patientAbsAlbumin = round((self.patientRelAlbumin * self.pt) / 100, 2)
        self.patientAbsAlpha1 = round((self.patientRelAlpha1 * self.pt) / 100, 2)
        self.patientAbsAlpha2 = round((self.patientRelAlpha2 * self.pt) / 100, 2)
        self.patientAbsBeta = round((self.patientRelBeta * self.pt) / 100, 2)
        self.patientAbsGamma = round((self.patientRelGamma * self.pt) / 100, 2)

    def getAbsAlbuminText(self):
        return str(self.patientAbsAlbumin) + " " + self.getAbsAlbuminFlag()

    def getAbsAlbuminFlag(self):
        return self.getFlagGeneric(self.albuminALow, self.albuminAHigh, self.patientAbsAlbumin)

    def getRelAlbuminText(self):
        return str(self.patientRelAlbumin) + "% " + self.getAbsAlbuminFlag()

    def getRelAlbuminFlag(self):
        return self.getFlagGeneric(self.albuminRLow, self.albuminRHigh, self.patientRelAlbumin)

    def getAbsAlpha1Text(self):
        return str(self.patientAbsAlpha1) + " " + self.getAbsAlpha1Flag()

    def getAbsAlpha1Flag(self):
        return self.getFlagGeneric(self.alpha1ALow, self.alpha1AHigh, self.patientAbsAlpha1)

    def getRelAlpha1Text(self):
        return str(self.patientRelAlpha1) + "% " + self.getRelAlpha1Flag()

    def getRelAlpha1Flag(self):
        return self.getFlagGeneric(self.alpha1RLow, self.alpha1RHigh, self.patientRelAlpha1)

    def getAbsAlpha2Text(self):
        return str(self.patientAbsAlpha2) + " " + self.getAbsAlpha2Flag()

    def getAbsAlpha2Flag(self):
        return self.getFlagGeneric(self.alpha2ALow, self.alpha2AHigh, self.patientAbsAlpha2)

    def getRelAlpha2Text(self):
        return str(self.patientRelAlpha2) + "% " + self.getRelAlpha2Flag()

    def getRelAlpha2Flag(self):
        return self.getFlagGeneric(self.alpha2RLow, self.alpha2RHigh, self.patientRelAlpha2)

    def getAbsBetaText(self):
        return str(self.patientAbsBeta) + " " + self.getAbsBetaFlag()

    def getAbsBetaFlag(self):
        return self.getFlagGeneric(self.betaALow, self.betaAHigh, self.patientAbsBeta)

    def getRelBetaText(self):
        return str(self.patientRelBeta) + "% " + self.getRelBetaFlag()

    def getRelBetaFlag(self):
        return self.getFlagGeneric(self.betaRLow, self.betaRHigh, self.patientRelBeta)

    def getAbsGammaText(self):
        return str(self.patientAbsGamma) + " " + self.getAbsGammaFlag()

    def getAbsGammaFlag(self):
        return self.getFlagGeneric(self.gammaALow, self.gammaAHigh, self.patientAbsGamma)

    def getRelGammaText(self):
        return str(self.patientRelGamma) + "% " + self.getRelGammaFlag()

    def getRelGammaFlag(self):
        return self.getFlagGeneric(self.gammaRLow, self.gammaRHigh, self.patientRelGamma)

    def getFlagGeneric(self, low, high, patient):
        if patient < low:
            return "L"
        if patient > high:
            return "H"
        return ""


class CommentInterpreter:
    def CM(thisRowData, H, B):

        new_comment = ''

        if H == 'Yes':
            new_comment = 'Compared to the study dated XXX, the previously identified monoclonal XXX band has decreased OR increased from XX g/dL to XX g/dL. Uninvolved gamma globulins are XXX decreased. No other significant changes are noted.'
        elif B == 'Yes':
            new_comment = 'Abnormal serum protein study due to the presence of a band in the gamma region that immunofixes as monoclonal XXXXXX. This band is present at a concentration of XXX g/dL. Uninvolved gamma globulins are XXX decreased XXX and no other significant abnormalities are noted. These results are consistent with a monoclonal gammopathy of undetermined significance (MGUS) although a B-cell dyscrasia is not excluded.'
        else:
            if (thisRowData.patientAbsAlbumin >= thisRowData.albuminALow) & (
                    thisRowData.patientAbsAlbumin <= thisRowData.albuminAHigh) & (
                    thisRowData.patientAbsAlpha1 > thisRowData.alpha1ALow) & (
                    thisRowData.patientAbsAlpha1 <= thisRowData.alpha1RHigh) & (
                    thisRowData.patientAbsAlpha2 > thisRowData.alpha2ALow) & (
                    thisRowData.patientAbsAlpha2 < thisRowData.alpha2AHigh) & (
                    thisRowData.patientAbsBeta > thisRowData.betaALow) & (
                    thisRowData.patientAbsBeta < thisRowData.betaAHigh) & (
                    thisRowData.patientAbsGamma > thisRowData.gammaALow) & (
                    thisRowData.patientAbsGamma < thisRowData.gammaAHigh):
                new_comment = 'A normal serum protein study.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (
                    thisRowData.patientRelAlpha1 > thisRowData.alpha1RHigh) & (
                    thisRowData.patientRelAlpha2 > thisRowData.alpha2RHigh):
                new_comment = 'Albumin is decreased while the relative concentrations of alpha-1 globulins and alpha-2 globulins are increased indicating an acute phase response to infection, inflammation or tissue injury.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt < thisRowData.proteinALow) & (
                    thisRowData.patientRelAlpha1 > thisRowData.alpha1RHigh) & (
                    thisRowData.patientRelAlpha2 > thisRowData.alpha2RHigh):
                new_comment = 'Total protein and albumin are decreased while the relative concentrations of alpha-1 globulins and alpha-2 globulins are increased indicating an acute phase response to infection, inflammation or tissue injury.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (
                    thisRowData.patientRelAlpha1 > thisRowData.alpha1RHigh) & (
                    thisRowData.patientRelAlpha2 >= thisRowData.alpha2RLow) & (
                    thisRowData.patientRelAlpha2 <= thisRowData.alpha2RHigh):
                new_comment = 'Albumin is decreased while the relative concentration of alpha-1 globulins is increased indicating an acute phase response to infection, inflammation or tissue injury.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt < thisRowData.proteinALow) & (
                    thisRowData.patientRelAlpha1 > thisRowData.alpha1RHigh) & (
                    thisRowData.patientRelAlpha2 >= thisRowData.alpha2RLow) & (
                    thisRowData.patientRelAlpha2 <= thisRowData.alpha2RHigh):
                new_comment = 'Total protein and albumin are decreased while the relative concentration of alpha-1 globulins is increased indicating an acute phase response to infection, inflammation or tissue injury.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (thisRowData.patientAbsGamma > thisRowData.gammaAHigh):
                new_comment = 'Albumin is decreased while there is diffuse (polyclonal) increase in gamma globulins indicating a chronic disease pattern.'
            elif (thisRowData.patientAbsAlbumin >= thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (thisRowData.patientAbsGamma > thisRowData.gammaAHigh):
                new_comment = 'There is a diffuse (polyclonal) increase in gamma globulins suggesting a chronic immune response or chronic disease pattern.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (
                    thisRowData.patientRelAlpha1 > thisRowData.alpha1RHigh) & (
                    thisRowData.patientRelAlpha2 > thisRowData.alpha2RHigh) & (
                    thisRowData.patientAbsGamma < thisRowData.gammaAHigh):
                new_comment = 'Albumin is decreased while gamma globulins are diffusely increased and alpha-1 globulins and alpha-2 globulins are relatively increased indicating a concomitant acute phase response and chronic disease pattern.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt < thisRowData.proteinALow) & (
                    thisRowData.patientRelAlpha1 > thisRowData.alpha1RHigh) & (
                    thisRowData.patientRelAlpha2 > thisRowData.alpha2RHigh) & (
                    thisRowData.patientAbsGamma > thisRowData.gammaAHigh):
                new_comment = 'Total protein and albumin are decreased while gamma globulins are diffusely increased and alpha-1 globulins and alpha-2 globulins are relatively increased indicating a concomitant acute phase response and chronic disease pattern.'
            elif (thisRowData.eta >= 65) & (thisRowData.patientAbsAlbumin >= thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (
                    thisRowData.patientAbsAlpha1 > thisRowData.alpha1ALow) & (
                    thisRowData.patientAbsAlpha1 <= thisRowData.alpha1RHigh) & (
                    thisRowData.patientAbsAlpha2 > thisRowData.alpha2AHigh):
                new_comment = 'Increased alpha-2 globulins may be due to increased haptoglobin in an acute phase response, increased alpha-2 macroglobulin in diabetes mellitus or may be a nonspecific finding most common in the elderly.'
            elif (thisRowData.eta < 65) & (thisRowData.patientAbsAlbumin >= thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (
                    thisRowData.patientAbsAlpha1 > thisRowData.alpha1ALow) & (
                    thisRowData.patientAbsAlpha1 <= thisRowData.alpha1RHigh) & (
                    thisRowData.patientAbsAlpha2 > thisRowData.alpha2AHigh):
                new_comment = 'Increased alpha-2 globulins may be due to increased haptoglobin in an acute phase response or increased alpha-2 macroglobulin in diabetes mellitus.'
            elif (thisRowData.eta >= 65) & (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow):
                new_comment = 'Albumin is decreased suggesting protein malnutrition although this may be a normal finding in the elderly.'
            elif (thisRowData.eta < 65) & (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow):
                new_comment = 'Albumin is decreased suggesting protein malnutrition.'
            elif (thisRowData.eta >= 65) & (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt < thisRowData.proteinALow):
                new_comment = 'Total protein and albumin are decreased suggesting protein malnutrition although this may be a normal finding in the elderly.'
            elif (thisRowData.eta < 65) & (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt < thisRowData.proteinALow):
                new_comment = 'Total protein and albumin are decreased suggesting protein malnutrition.'
            elif (thisRowData.patientAbsAlbumin >= thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (
                    thisRowData.patientAbsAlpha1 > thisRowData.alpha1ALow) & (
                    thisRowData.patientAbsAlpha2 < thisRowData.alpha2ALow) & (
                    thisRowData.patientAbsGamma >= thisRowData.gammaALow) & (
                    thisRowData.patientAbsGamma <= thisRowData.gammaAHigh):
                new_comment = 'Alpha-2 globulins are decreased most likely due to decreased hathisRowData.ptoglobin and/or alpha-2 macroglobulin.'
            elif (thisRowData.patientAbsAlbumin < thisRowData.albuminALow) & (
                    thisRowData.pt < thisRowData.proteinALow) & (thisRowData.patientAbsGamma < thisRowData.gammaALow):
                new_comment = 'Total protein, gamma globulins, and albumin are decreased suggesting protein malnutrition.'
            elif (thisRowData.patientAbsAlbumin > thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (
                    thisRowData.patientAbsGamma < thisRowData.gammaALow) & (
                    thisRowData.patientAbsGamma >= 0.4):
                new_comment = 'Gamma globulins are slightly decreased.'
            elif (thisRowData.patientAbsAlbumin > thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (thisRowData.patientAbsGamma < 0.4) & (
                    thisRowData.patientAbsGamma >= 0.2):
                new_comment = 'Gamma globulins are moderately decreased.'
            elif (thisRowData.patientAbsAlbumin > thisRowData.albuminALow) & (
                    thisRowData.pt >= thisRowData.proteinALow) & (thisRowData.patientAbsGamma < 0.2):
               new_comment = 'Gamma globulins are markedly decreased.'
            elif (thisRowData.patientAbsAlbumin > thisRowData.albuminAHigh) & (
                    thisRowData.patientAbsAlpha1 > thisRowData.alpha1ALow) & (
                    thisRowData.patientAbsAlpha1 < thisRowData.alpha1RHigh) & (
                    thisRowData.patientAbsAlpha2 > thisRowData.alpha2ALow) & (
                    thisRowData.patientAbsAlpha2 < thisRowData.alpha2AHigh) & (
                    thisRowData.patientAbsBeta > thisRowData.betaALow) & (
                    thisRowData.patientAbsBeta < thisRowData.betaAHigh) & (
                    thisRowData.patientAbsGamma > thisRowData.gammaALow) & (
                    thisRowData.patientAbsGamma < thisRowData.gammaAHigh):
                new_comment = 'Albumin is increased.'
            else:
                new_comment = 'No comment available for this case.'
        return new_comment

database_connection = DatabaseConnection()
gui = GUI(database_connection)
gui.mainloop()
database_connection.close_database_connection()
