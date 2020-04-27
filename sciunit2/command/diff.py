#Note: Converted
from __future__ import absolute_import

from sciunit2.command import AbstractCommand
#from sciunit2.command.mixin import CommitMixin
from sciunit2.exceptions import CommandLineError, CommandError
from sciunit2.command.context import CheckoutContext
#from sciunit2.cdelog import DetachedExecution
import sciunit2.workspace
from sciunit2.util import quoted_format

from getopt import getopt
import os
import subprocess
from subprocess import PIPE


class DiffCommand(AbstractCommand):
    name = 'diff'

    @property
    def usage(self):
        return [('diff <execution id1> <execution id2>',
                 'Compare two execution containers file by file. ')]

    def run(self, args):
        # command is run like diff <execution id1> <execution id2>
        optlist, args = getopt(args, '')
        if len(args) <= 1:
            raise CommandLineError
        emgr, repo = sciunit2.workspace.current()
        # emgr is ExecutionManager, repo is Vvpkg
        # Vvpkg is the de-duplication engine

        with emgr.exclusive():  # exclusive performs a lock on the berkeleydb instance
            orig1 = emgr.get(args[0]).cmd
            diffdir = os.path.join(repo.location, 'Diff')  # repo.location is the project dir
            repo.checkout_Diff(args[0])
            orig2 = emgr.get(args[1]).cmd
            repo.checkout_Diff(args[1])
            cmd = quoted_format('rsync -nai --delete {0}/ {1}/', args[0], args[1])
            p = subprocess.Popen(cmd, shell=True, cwd=diffdir, stderr=PIPE, stdout=PIPE)
            out, err = p.communicate()
            p_status = p.wait()
            # process output by rsync command
            new_e1, new_e2, size_changed, time_changed, perms_changed = \
                self.parse_rsync(out, args[0], args[1], diffdir)
            output = "Files only in e1:\n" + '\n'.join(new_e1) + "\n\n" \
                    "Files only in e2:\n" + '\n'.join(new_e2) + "\n\n" \
                    "Files with changed size:\n" + '\n'.join(size_changed) + "\n\n" \
                    "Files with changed modified time:\n" + '\n'.join(time_changed) + "\n\n" \
                    "Files with changed permissions:\n" + '\n'.join(perms_changed) + "\n\n"

            return output, err

    """
    detail on output format of rsync could be found at:
     https://linux.die.net/man/1/rsync 
     
     output format:
     Files only in e1:
     Files only in e2:
     Files with changed size:
     Files with changed modified time:
     Files with changed permissions:
    """
    @staticmethod
    def parse_rsync(out, e1, e2, diffdir):
        # each line starts with YXcstpoguax followed by file/dir name
        out_str = out.decode("utf-8").strip()
        lines = out_str.split("\n")
        new_e1 = []
        new_e2 = []
        size_changed = []
        time_changed = []
        perms_changed = []
        for line in lines:
            splits = line.split()
            YXcstpoguax = splits[0].strip()
            file_name = splits[1].strip()
            update_type = YXcstpoguax[0]
            file_type = YXcstpoguax[1]
            # TODO: size of YXcstpoguax might not be 11 letters long,
            #  as in '*deleting'
            file_size = YXcstpoguax[3]
            modified_time = YXcstpoguax[4]
            file_perms = YXcstpoguax[5]

            if update_type == '*':    # contains a message
                # case 1: *deleting (file is present in e2, not e1)
                # these are the new files in e2
                if YXcstpoguax[1:] == "deleting":
                    new_e2.append(file_name)

            # '.' is for changed but not being updated
            # '>' local change to take place
            elif update_type == '.' or update_type == '>':
                if file_type == 'f':         # it is a file
                    # case 1: '>f+++++++++'
                    # case 2: '.f.stp.....'
                    if YXcstpoguax[2] == '+':   # new file in e1
                        new_e1.append(file_name)
                    if file_size == 's':      # size of file changed
                        size_changed.append(file_name)
                    if modified_time == 't':  # modified time of file changed
                        time_changed.append(file_name)
                    if file_perms == 'p':     # permissions of file changed
                        perms_changed.append(file_name)
            else:                       # rest of the cases not handled right now
                continue

        return new_e1, new_e2, size_changed, time_changed, perms_changed

    def note(self, aList):
        return "\n %s \n %s \n" % (aList[0].decode('utf-8'), aList[1].decode('utf-8'))

        #emgr, repo = sciunit2.workspace.current()
        #pkgdir = os.path.join(repo.location, 'cde-package')
        #with emgr.exclusive():
        #    for cmd in DetachedExecution(pkgdir).getcmd():
        #        rev = emgr.add(cmd)
        #        return self.do_commit(pkgdir, rev, emgr, repo)
        #    else:
        #        raise CommandError('nothing to commit')