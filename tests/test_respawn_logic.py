import unittest

from game.respawn import PLAYER_RESPAWN_DELAY_MS, should_auto_respawn


class RespawnLogicTests(unittest.TestCase):
    def test_respawns_after_delay_when_teammate_is_alive(self):
        self.assertTrue(
            should_auto_respawn(0, PLAYER_RESPAWN_DELAY_MS, True, PLAYER_RESPAWN_DELAY_MS)
        )

    def test_does_not_respawn_before_delay(self):
        self.assertFalse(
            should_auto_respawn(0, PLAYER_RESPAWN_DELAY_MS - 1, True, PLAYER_RESPAWN_DELAY_MS)
        )

    def test_does_not_respawn_without_living_teammate(self):
        self.assertFalse(
            should_auto_respawn(0, PLAYER_RESPAWN_DELAY_MS, False, PLAYER_RESPAWN_DELAY_MS)
        )


if __name__ == '__main__':
    unittest.main()
