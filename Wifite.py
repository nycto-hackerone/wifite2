#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

from py.Configuration import Configuration
from py.Scanner import Scanner
from py.Color import Color
from py.AttackWEP import AttackWEP
from py.AttackWPA import AttackWPA
from py.AttackWPS import AttackWPS
from py.CrackResult import CrackResult
from py.Handshake import Handshake
from py.CrackHandshake import CrackHandshake
from py.Process import Process

from json import loads
import os
from sys import exit

class Wifite(object):

    def main(self):
        ''' Either performs action based on arguments, or starts attack scanning '''

        if os.getuid() != 0:
            Color.pl('{!} {R}error: {O}wifite{R} must be run as {O}root{W}')
            Color.pl('{!} {O}re-run as: sudo ./Wifite.py{W}')
            Configuration.exit_gracefully(0)

        self.dependency_check()

        Configuration.initialize(load_interface=False)

        if Configuration.show_cracked:
            self.display_cracked()

        elif Configuration.check_handshake:
            self.check_handshake(Configuration.check_handshake)
        elif Configuration.crack_handshake:
            CrackHandshake()
        else:
            Configuration.get_interface()
            self.run()

    def dependency_check(self):
        ''' Check that required programs are installed '''
        required_apps = ['airmon-ng', 'iwconfig', 'ifconfig', 'aircrack-ng', 'aireplay-ng', 'airodump-ng', 'tshark']
        optional_apps = ['packetforge-ng', 'reaver', 'bully', 'cowpatty', 'pyrit', 'stdbuf', 'macchanger']
        missing_required = False
        missing_optional = False

        for app in required_apps:
            if not Process.exists(app):
                missing_required = True
                Color.pl('{!} {R}error: required app {O}%s{R} was not found' % app)

        for app in optional_apps:
            if not Process.exists(app):
                missing_optional = True
                Color.pl('{!} {O}warning: recommended app {R}%s{O} was not found' % app)

        if missing_required:
            Color.pl('{!} {R}required app(s) were not found, exiting.{W}')
            exit(-1)

        if missing_optional:
            Color.pl('{!} {O}recommended app(s) were not found')
            Color.pl('{!} {O}wifite may not work as expected{W}')

    def display_cracked(self):
        ''' Show cracked targets from cracked.txt '''
        Color.pl('{+} displaying {C}cracked target(s){W}')
        name = CrackResult.cracked_file
        if not os.path.exists(name):
            Color.pl('{!} {O}file {C}%s{O} not found{W}' % name)
            return
        with open(name, 'r') as fid:
            json = loads(fid.read())
        for idx, item in enumerate(json, start=1):
            Color.pl('\n{+} Cracked target #%d:' % (idx))
            cr = CrackResult.load(item)
            cr.dump()

    def check_handshake(self, capfile):
        ''' Analyzes .cap file for handshake '''
        if capfile == '<all>':
            Color.pl('{+} checking all handshakes in {G}"./hs"{W} directory\n')
            try:
                capfiles = [os.path.join('hs', x) for x in os.listdir('hs') if x.endswith('.cap')]
            except OSError, e:
                capfiles = []
            if len(capfiles) == 0:
                Color.pl('{!} {R}no .cap files found in {O}"./hs"{W}\n')
        else:
            capfiles = [capfile]
        for capfile in capfiles:
            Color.pl('{+} checking for handshake in .cap file {C}%s{W}' % capfile)
            if not os.path.exists(capfile):
                Color.pl('{!} {O}.cap file {C}%s{O} not found{W}' % capfile)
                return
            hs = Handshake(capfile, bssid=Configuration.target_bssid, essid=Configuration.target_essid)
            hs.analyze()
            Color.pl('')

    def run(self):
        '''
            Main program.
            1) Scans for targets, asks user to select targets
            2) Attacks each target
        '''
        s = Scanner()
        if s.target:
            # We found the target we want
            targets = [s.target]
        else:
            targets = s.select_targets()

        attacked_targets = 0
        targets_remaining = len(targets)
        for idx, t in enumerate(targets, start=1):
            attacked_targets += 1
            targets_remaining -= 1

            Color.pl('\n{+} ({G}%d{W}/{G}%d{W})' % (idx, len(targets)) +
                     ' starting attacks against {C}%s{W} ({C}%s{W})'
                % (t.bssid, t.essid if t.essid_known else "{O}ESSID unknown"))
            if 'WEP' in t.encryption:
                attack = AttackWEP(t)
            elif 'WPA' in t.encryption:
                if t.wps:
                    attack = AttackWPS(t)
                    result = False
                    try:
                        result = attack.run()
                    except Exception, e:
                        Color.pl("\n{!} {R}Error: {O}%s" % str(e))
                        if Configuration.verbose > 0 or True:
                            Color.pl('\n{!} {O}Full stack trace below')
                            from traceback import format_exc
                            Color.p('\n{!}    ')
                            err = format_exc().strip()
                            err = err.replace('\n', '\n{!} {C}   ')
                            err = err.replace('  File', '{W}File')
                            err = err.replace('  Exception: ', '{R}Exception: {O}')
                            Color.pl(err)
                    except KeyboardInterrupt:
                        Color.pl('\n{!} {O}interrupted{W}\n')
                        if not self.user_wants_to_continue(targets_remaining, 1):
                            break

                    if result and attack.success:
                        # We cracked it.
                        attack.crack_result.save()
                        continue
                    else:
                        # WPS failed, try WPA handshake.
                        attack = AttackWPA(t)
                else:
                    # Not using WPS, try WPA handshake.
                    attack = AttackWPA(t)
            else:
                Color.pl("{!} {R}Error: {O}unable to attack: encryption not WEP or WPA")
                continue

            try:
                attack.run()
            except Exception, e:
                Color.pl("\n{!} {R}Error: {O}%s" % str(e))
                if Configuration.verbose > 0 or True:
                    Color.pl('\n{!} {O}Full stack trace below')
                    from traceback import format_exc
                    Color.p('\n{!}    ')
                    err = format_exc().strip()
                    err = err.replace('\n', '\n{!} {C}   ')
                    err = err.replace('  File', '{W}File')
                    err = err.replace('  Exception: ', '{R}Exception: {O}')
                    Color.pl(err)
            except KeyboardInterrupt:
                Color.pl('\n{!} {O}interrupted{W}\n')
                if not self.user_wants_to_continue(targets_remaining):
                    break

            if attack.success:
                attack.crack_result.save()
        Color.pl("{+} Finished attacking {C}%d{W} target(s), exiting" % attacked_targets)


    def print_banner(self):
        """ Displays ASCII art of the highest caliber.  """
        Color.pl(r'''
{G}  .     {GR}{D}     {W}{G}     .    {W}
{G}.´  ·  .{GR}{D}     {W}{G}.  ·  `.  {G}wifite {D}%s{W}
{G}:  :  : {GR}{D} (¯) {W}{G} :  :  :  {W}{D}automated wireless auditor
{G}`.  ·  `{GR}{D} /¯\ {W}{G}´  ·  .´  {C}{D}https://github.com/derv82/wifite2
{G}  `     {GR}{D}/¯¯¯\{W}{G}     ´    {W}
''' % Configuration.version)

    def user_wants_to_continue(self, targets_remaining, attacks_remaining=0):
        ''' Asks user if attacks should continue onto other targets '''
        if attacks_remaining == 0 and targets_remaining == 0:
            # No targets or attacksleft, drop out
            return

        prompt_list = []
        if attacks_remaining > 0:
            prompt_list.append(Color.s('{C}%d{W} attack(s)' % attacks_remaining))
        if targets_remaining > 0:
            prompt_list.append(Color.s('{C}%d{W} target(s)' % targets_remaining))
        prompt = ' and '.join(prompt_list)
        Color.pl('{+} %s remain, do you want to continue?' % prompt)

        prompt = Color.s('{+} type {G}c{W} to {G}continue{W}' +
                         ' or {R}s{W} to {R}stop{W}: ')

        if raw_input(prompt).lower().startswith('s'):
            return False
        else:
            return True


if __name__ == '__main__':
    w = Wifite()
    try:
        w.print_banner()
        w.main()
    except Exception, e:
        Color.pl('\n{!} {R}Error:{O} %s{W}' % str(e))
        if Configuration.verbose > 0 or True:
            Color.pl('\n{!} {O}Full stack trace below')
            from traceback import format_exc
            Color.p('\n{!}    ')
            err = format_exc().strip()
            err = err.replace('\n', '\n{!} {C}   ')
            err = err.replace('  File', '{W}File')
            err = err.replace('  Exception: ', '{R}Exception: {O}')
            Color.pl(err)
        Color.pl('\n{!} {R}Exiting{W}\n')
    except KeyboardInterrupt:
        Color.pl('\n{!} {O}interrupted, shutting down...{W}')
    Configuration.exit_gracefully(0)
