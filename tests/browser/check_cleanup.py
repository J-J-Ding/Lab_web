"""Fault injection verifies real isolated resources are cleaned if class startup fails."""
from io import StringIO
import unittest
from unittest.mock import patch

import test_auth_browser
from support import Environment


def main():
    environments=[]
    def create():
        env=Environment()
        environments.append(env)
        return env
    class StartupFailure(test_auth_browser.AuthBrowserTests):
        pass
    try:
        with patch('test_auth_browser.Environment',side_effect=create), patch('test_auth_browser.sync_playwright',side_effect=RuntimeError('injected startup failure')):
            result=unittest.TextTestRunner(stream=StringIO()).run(unittest.TestSuite([StartupFailure('test_auth_pages_exist')]))
        assert len(result.errors)==1, 'The injected startup failure was not observed'
        assert len(environments)==1
        assert not environments[0].created_container and not environments[0].created_database, 'Isolated test resources remained after startup failure'
        print('Startup failure cleanup: PASS; disposable container/database removed.')
    finally:
        for env in environments:
            env.close()


if __name__=='__main__':
    main()
