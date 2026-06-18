import os
import unittest
from agent.tools import calculate, read_file, write_file, WORKSPACE_ROOT

class TestAgentTools(unittest.TestCase):
    
    def test_calculate_basic(self):
        self.assertEqual(calculate("2 + 3"), "5")
        self.assertEqual(calculate("10 * (2 + 3)"), "50")
        self.assertEqual(calculate("5**2"), "25")
        self.assertEqual(calculate("10 / 2"), "5.0")
        self.assertEqual(calculate("15 % 4"), "3")

    def test_calculate_dangerous_expressions(self):
        # Division by zero
        self.assertIn("Error", calculate("10 / 0"))
        # Using variables/unsupported functions
        self.assertIn("Error", calculate("x + 1"))
        self.assertIn("Error", calculate("import os"))
        self.assertIn("Error", calculate("eval('2+2')"))
        # Exponentiation checks
        self.assertIn("Error", calculate("10000**10000"))

    def test_file_io_safety(self):
        # Attempt traversal outside workspace
        self.assertIn("Error", read_file("../../etc/passwd"))
        self.assertIn("Error", write_file("../../../malicious.txt", "content"))
        
        # Test safe reads and writes inside workspace
        test_file = "test_run_data.txt"
        test_path = os.path.join(WORKSPACE_ROOT, test_file)
        
        try:
            write_res = write_file(test_file, "Hello World ReAct")
            self.assertIn("Success", write_res)
            
            read_res = read_file(test_file)
            self.assertEqual(read_res, "Hello World ReAct")
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

if __name__ == "__main__":
    unittest.main()
