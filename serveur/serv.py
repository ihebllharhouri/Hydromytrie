import http.server
import socketserver
from urllib.parse import urlparse, parse_qs, unquote
import sqlite3
import time
import json
import matplotlib.pyplot as plt
import datetime as dt
import matplotlib.dates as pltd


conn = sqlite3.connect('./client/hydrometrie.db')
parse = conn.cursor()


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    static_dir = '/client'

    def init_params(self):
        info = urlparse(self.path)
        self.path_info = info.path.split('/')[1:]
        self.query_string = info.query
        self.params = parse_qs(info.query)

    def do_GET(self):
        self.init_params()
# Code présent dans le TD avec quelques modifications
        if self.path_info[0] == "location":
            parse.execute("SELECT CdStationHydro,X,Y,LbStationHydro, CdStationHydroAncienRef FROM 'stationhydro-2022'")
            r = parse.fetchall()

            data=[{'id':x[0],'lon':x[1],'lat':x[2], 'name':x[3], 'oldid':x[4]} for x in r]
            parse.execute("SELECT DISTINCT CodesiteHydro3 FROM 'Hydrometrie-2022'")
            r = parse.fetchall()
            r = [x[0] for x in r]
            for x in data:
#                 On vérifie s'il y a une correspondance de l'identifiant dans les deux tableaux, car il se peut qu'une station ne soit pas présente dans 'Hydrométrie-2022 bien qu'elle ait un identifiant ancien', sinon on met None à la place de l'identifiant
                if x['oldid'] not in r:
                    x['oldid'] = None
            self.send_json(data)

# Affichage de la description
        elif self.path_info[0] == "description":
            parse.execute("SELECT CdStationHydro,X,Y FROM 'stationhydro-2022'")
            r = parse.fetchall()
            data=[{'id':x[0],'lon':x[1],'lat':x[2]} for x in r]
            for c in data:
                if c['id'] == self.path_info[1]:
                    self.send_json({'desc':str(c['lat']) + ', '+ str(c['lon'])})
                    break

#  Courbe ou comparaison
        elif self.path_info[0] == 'courbe':
            self.send_courbe()

        elif self.path_info[0] == 'comparaison':
            self.send_comparaison()


        else:
            self.path = self.static_dir + self.path
            http.server.SimpleHTTPRequestHandler.do_GET(self)

    def send(self,body,headers=[]):

        encoded = bytes(body, 'UTF-8')

        self.send_response(200)

        [self.send_header(*t) for t in headers]
        self.send_header('Content-Length',int(len(encoded)))
        self.end_headers()

        self.wfile.write(encoded)

# Fonction pour envoyer la courbe quand on clique sur 'Afficher la courbe'
    def send_courbe(self):
#         Fonction pour convertir la date formatée par le site en date utilisable par matplotlib
        def date_good(x):
            return str(x[6:]) + '-' + str(x[3:5]) + '-' + str(x[:2])
        idnum = self.path_info[1]
        dd = self.path_info[2]
        df = self.path_info[3]
        parse.execute("SELECT Date,CodeSiteHydro3, `QMJvalidé(m3/s)` FROM 'Hydrometrie-2022' WHERE CodeSiteHydro3=? ORDER BY Date",[idnum])
        r = parse.fetchall()
        r = [list(x) for x in r]
#         On récupère dans la BDD la liste des valeurs de débits des rivières
        X = sorted([dt.date(int(date_good(x[0])[:4]),int(date_good(x[0])[5:7]),int(date_good(x[0])[8:])) for x in r if (date_good(x[0]) >= dd) and (date_good(x[0]) <= df)])
        QMJ = [x[2] for x in r if (date_good(x[0]) >= dd) and (date_good(x[0]) <= df)]
#         On le plot grâce à matplotlib en formattant les axes pour afficher la date en abscisse
        fig, ax = plt.subplots(figsize=(18,6))
        ax.plot(X,QMJ)


        ax.set(title='Débit moyen journalier en m3/s', xlabel='Date', ylabel='QMJ(m3/s)')
        loc_major = pltd.YearLocator()
        loc_minor = pltd.MonthLocator()
        ax.xaxis.set_major_locator(loc_major)
        ax.xaxis.set_minor_locator(loc_minor)
        format_major = pltd.DateFormatter('%d/%m/%Y')
        ax.xaxis.set_major_formatter(format_major)
        ax.xaxis.set_tick_params(labelsize=10)
        locator = pltd.AutoDateLocator(interval_multiples=True)
        ax.xaxis.set_major_locator(locator)

#         On enrigistre la courbe dans le dossier 'courbes' avec le format 'debit_[identifiant du lieu].png'
        fichier = 'courbes/debit_'
        if len(self.path_info) > 1:
            fichier = fichier + self.path_info[1]
        fichier = fichier +'.png'
        plt.savefig('client/{}'.format(fichier),bbox_inches = 'tight')
        plt.close()

        parse.execute("SELECT LbStationHydro FROM 'stationhydro-2022' WHERE CdStationHydroAncienRef=? LIMIT 1",[idnum])
        r = parse.fetchall()
#         On récupère le nom du lieu à partir de son identifiant dans l'autre tableau pour l'envoyer au à la page web
        data = {'src':fichier,'lieu':r[0][0]}
        self.send_json(data)

# Fonction pour la comparaison
    def send_comparaison(self):
        def date_good(x):
            return str(x[6:]) + '-' + str(x[3:5]) + '-' + str(x[:2])
#             On récupère les varirables d'intérêt à partir de l'URL de la requête
        idnum1 = self.path_info[1]
        idnum2 = self.path_info[3]
        name1 = unquote(self.path_info[2])
        name2 = unquote(self.path_info[4])
        dd = self.path_info[5]
        df = self.path_info[6]


        fig, ax = plt.subplots(figsize=(18,6))
#         On fait un premier plot pour le premier site
        parse.execute("SELECT Date,CodeSiteHydro3, `QMJvalidé(m3/s)` FROM 'Hydrometrie-2022' WHERE CodeSiteHydro3=? ORDER BY Date",[idnum1])
        r = parse.fetchall()
        r = [list(x) for x in r]
        X = sorted([dt.date(int(date_good(x[0])[:4]),int(date_good(x[0])[5:7]),int(date_good(x[0])[8:])) for x in r if (date_good(x[0]) >= dd) and (date_good(x[0]) <= df)])
        QMJ = [x[2] for x in r if (date_good(x[0]) >= dd) and (date_good(x[0]) <= df)]
        ax.plot(X,QMJ,label=name1,color='blue')
#         Un second plot pour le second site
        parse.execute("SELECT Date,CodeSiteHydro3, `QMJvalidé(m3/s)` FROM 'Hydrometrie-2022' WHERE CodeSiteHydro3=? ORDER BY Date",[idnum2])
        r = parse.fetchall()
        r = [list(x) for x in r]
        QMJ = [x[2] for x in r if (date_good(x[0]) >= dd) and (date_good(x[0]) <= df)]
        ax.plot(X,QMJ,label=name2,color='#991515')
        ax.legend()

#         Formattage des axes
        ax.set(title='Débit moyen journalier en m3/s', xlabel='Date', ylabel='QMJ(m3/s)')
        loc_major = pltd.YearLocator()
        loc_minor = pltd.MonthLocator()
        ax.xaxis.set_major_locator(loc_major)
        ax.xaxis.set_minor_locator(loc_minor)
        format_major = pltd.DateFormatter('%d/%m/%Y')
        ax.xaxis.set_major_formatter(format_major)
        ax.xaxis.set_tick_params(labelsize=10)
        locator = pltd.AutoDateLocator(interval_multiples=True)
        ax.xaxis.set_major_locator(locator)

#         Enregistrement du fichier au format 'debit_comparaison_[identifiant premier site]_[identifiant second site].png'
        fichier = 'courbes/debit_comparaison'
        if len(self.path_info) > 1:
            fichier = fichier + '_' + idnum1 + '_' + idnum2
        fichier = fichier +'.png'
        plt.savefig('client/{}'.format(fichier),bbox_inches = 'tight')
        plt.close()

        r = parse.fetchall()
        data = {'src':fichier,'lieu':name1 +' et '+name2}
        self.send_json(data)


    def send_json(self,data,headers=[]):
        body = bytes(json.dumps(data),'utf-8')
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',int(len(body)))
        [self.send_header(*t) for t in headers]
        self.end_headers()
        self.wfile.write(body)














httpd = socketserver.TCPServer(("", 8080), RequestHandler)
httpd.serve_forever()