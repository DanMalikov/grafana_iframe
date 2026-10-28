"""Check the demo records without changing existing MySQL data."""

import unittest

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Company, Device, User


class SeedTests(unittest.TestCase):
    def test_demo_companies_users_and_devices(self) -> None:
        expected_devices = {
            "1": {"0030014467", "10"},
            "2": {"1140000464", "1050"},
        }
        with SessionLocal() as session:
            for company_id, device_ids in expected_devices.items():
                company = session.get(Company, company_id)
                self.assertIsNotNone(company)
                self.assertEqual(company.name, f"Company {company_id}")

                users = session.scalars(
                    select(User).where(User.company_id == company_id)
                ).all()
                roles = {user.username: user.business_role for user in users}
                self.assertEqual(roles[f"analyst{company_id}"], "analyst")
                self.assertEqual(roles[f"director{company_id}"], "director")

                actual_devices = set(
                    session.scalars(
                        select(Device.id).where(Device.company_id == company_id)
                    )
                )
                self.assertTrue(device_ids <= actual_devices)


if __name__ == "__main__":
    unittest.main()
