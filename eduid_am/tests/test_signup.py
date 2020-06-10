from copy import deepcopy
from datetime import date, timedelta

import bson

from eduid_common.config.workers import AmConfig
from eduid_userdb.exceptions import UserDoesNotExist, UserHasUnknownData
from eduid_userdb.fixtures.users import mocked_user_standard
from eduid_userdb.signup import SignupUser

from eduid_am.ams import eduid_signup
from eduid_am.testing import AMTestCase
from eduid_am.tests.test_proofing_fetchers import USER_DATA


M = mocked_user_standard.to_dict()


class AttributeFetcherTests(AMTestCase):
    def setUp(self):
        am_settings = {'want_mongo_uri': True, 'new_user_date': '2001-01-01'}
        super(AttributeFetcherTests, self).setUp(am_settings=am_settings)

        self.fetcher = eduid_signup(self.am_settings)

        for userdoc in self.amdb._get_all_docs():
            signup_user = SignupUser(data=userdoc)
            self.fetcher.private_db.save(signup_user, check_sync=False)

    def test_invalid_user(self):
        with self.assertRaises(UserDoesNotExist):
            self.fetcher.fetch_attrs(bson.ObjectId('000000000000000000000000'))

    def test_existing_user_from_db(self):

        res = self.fetcher.fetch_attrs(bson.ObjectId(M['_id']))

        self.assertEqual(res['$set']['eduPersonPrincipalName'], 'hubba-bubba')
        self.assertEqual(res['$set']['mailAliases'][0]['email'], 'johnsmith@example.com')
        self.assertEqual(res['$set']['mailAliases'][0]['primary'], True)
        self.assertEqual(res['$set']['mailAliases'][0]['verified'], True)
        self.assertEqual(res['$set']['mailAliases'][1]['email'], 'johnsmith2@example.com')
        self.assertEqual(res['$set']['mailAliases'][1]['primary'], False)
        self.assertEqual(res['$set']['mailAliases'][1]['verified'], True)
        self.assertEqual(res['$set']['mailAliases'][2]['email'], 'johnsmith3@example.com')
        self.assertEqual(res['$set']['mailAliases'][2]['primary'], False)
        self.assertEqual(res['$set']['mailAliases'][2]['verified'], False)
        self.assertEqual(res['$set']['passwords'][0]['credential_id'], '112345678901234567890123')
        self.assertEqual(res['$set']['passwords'][0]['is_generated'], False)
        self.assertEqual(res['$set']['passwords'][0]['salt'], '$NDNv1H1$9c810d852430b62a9a7c6159d5d64c41c3831846f81b6799b54e1e8922f11545$32$32$')

    def test_existing_user(self):
        user_data = deepcopy(USER_DATA)
        user_data['mail'] = 'johnsmith@example.com'
        user_data['mailAliases'] = [{'verified': True, 'email': 'johnsmith@example.com'}]
        del user_data['passwords']
        user = SignupUser(data=user_data)
        self.fetcher.private_db.save(user)
        with self.assertRaises(ValueError):
            self.fetcher.fetch_attrs(bson.ObjectId(user.user_id))

    def test_user_without_aliases(self):
        user_data = deepcopy(USER_DATA)
        user_data['mail'] = 'johnsmith@example.com'
        del user_data['passwords']
        user = SignupUser(data=user_data)
        self.fetcher.private_db.save(user)
        with self.assertRaises(ValueError):
            self.fetcher.fetch_attrs(bson.ObjectId(user.user_id))

    def test_user_finished_and_removed(self):
        user_data = deepcopy(USER_DATA)
        user_data['mail'] = 'john@example.com'
        user_data['mailAliases'] = [{'email': 'john@example.com', 'verified': True,}]
        user_data['passwords'] = [{'id': '123', 'salt': '456',}]
        user = SignupUser(data=user_data)
        self.fetcher.private_db.save(user)
        attrs = self.fetcher.fetch_attrs(user.user_id)
        self.assertEqual(
            attrs,
            {
                '$set': {
                    'eduPersonPrincipalName': 'test-test',
                    'mailAliases': [{'verified': True, 'primary': True, 'email': 'john@example.com'}],
                    'passwords': [{'credential_id': u'123', 'is_generated': False, 'salt': u'456',}],
                }
            },
        )

    def test_malicious_attributes(self):
        user_data = deepcopy(USER_DATA)
        user_data['foo'] = 'bar'
        user_data['mail'] = 'john@example.com'
        user_data['mailAliases'] = [{'email': 'john@example.com', 'verified': True,}]
        user_data['passwords'] = [{'id': '123', 'salt': '456',}]
        with self.assertRaises(UserHasUnknownData):
            SignupUser(data=user_data)
