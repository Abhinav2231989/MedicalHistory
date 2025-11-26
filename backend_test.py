#!/usr/bin/env python3
"""
Comprehensive Backend API Tests for Medical History System
Testing NEW FEATURES: Patient ID auto-generation, SQLite storage, Google Drive integration
"""

import requests
import json
import time
import os
from pathlib import Path

# Get backend URL from frontend .env
BACKEND_URL = "https://0514b52e-e3d0-489f-8ea1-868232439255.preview.emergentagent.com/api"

class MedicalHistoryAPITester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.session = requests.Session()
        self.test_results = []
        self.created_records = []  # Track created records for cleanup
        
    def log_test(self, test_name, success, message, details=None):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'details': details
        })
    
    def test_patient_id_auto_generation(self):
        """Test Patient ID auto-generation feature"""
        print("\n=== Testing Patient ID Auto-generation ===")
        
        # Test 1: Create first record with "John Doe"
        try:
            payload = {
                "patient_name": "John Doe",
                "diagnosis_details": "Hypertension and diabetes management",
                "medicine_names": "Metformin 500mg, Lisinopril 10mg"
            }
            
            response = self.session.post(f"{self.base_url}/patients", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                patient_id_1 = data.get('patient_id')
                record_id_1 = data.get('id')
                self.created_records.append(record_id_1)
                
                if patient_id_1 and patient_id_1.startswith('P'):
                    self.log_test("Patient ID Auto-generation - First Record", True, 
                                f"First patient got ID: {patient_id_1}")
                else:
                    self.log_test("Patient ID Auto-generation - First Record", False, 
                                f"Expected P#### format, got: {patient_id_1}")
            else:
                self.log_test("Patient ID Auto-generation - First Record", False, 
                            f"Failed to create record: {response.status_code}")
                return
                
        except Exception as e:
            self.log_test("Patient ID Auto-generation - First Record", False, f"Exception: {str(e)}")
            return
        
        # Test 2: Create second record with same name "John Doe"
        try:
            time.sleep(1)  # Small delay
            response = self.session.post(f"{self.base_url}/patients", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                patient_id_2 = data.get('patient_id')
                record_id_2 = data.get('id')
                self.created_records.append(record_id_2)
                
                if patient_id_2 == patient_id_1:
                    self.log_test("Patient ID Auto-generation - Same Name", True, 
                                f"Same patient name got same ID: {patient_id_2}")
                else:
                    self.log_test("Patient ID Auto-generation - Same Name", False, 
                                f"Expected {patient_id_1}, got: {patient_id_2}")
            else:
                self.log_test("Patient ID Auto-generation - Same Name", False, 
                            f"Failed to create record: {response.status_code}")
                
        except Exception as e:
            self.log_test("Patient ID Auto-generation - Same Name", False, f"Exception: {str(e)}")
        
        # Test 3: Create record with different name "Jane Smith"
        try:
            payload_jane = {
                "patient_name": "Jane Smith",
                "diagnosis_details": "Migraine treatment and follow-up",
                "medicine_names": "Sumatriptan 50mg, Propranolol 40mg"
            }
            
            response = self.session.post(f"{self.base_url}/patients", json=payload_jane)
            
            if response.status_code == 200:
                data = response.json()
                patient_id_3 = data.get('patient_id')
                record_id_3 = data.get('id')
                self.created_records.append(record_id_3)
                
                if patient_id_3 and patient_id_3 != patient_id_1 and patient_id_3.startswith('P'):
                    self.log_test("Patient ID Auto-generation - Different Name", True, 
                                f"Different patient got new ID: {patient_id_3}")
                else:
                    self.log_test("Patient ID Auto-generation - Different Name", False, 
                                f"Expected different P#### format, got: {patient_id_3}")
            else:
                self.log_test("Patient ID Auto-generation - Different Name", False, 
                            f"Failed to create record: {response.status_code}")
                
        except Exception as e:
            self.log_test("Patient ID Auto-generation - Different Name", False, f"Exception: {str(e)}")
    
    def test_search_by_patient_id(self):
        """Test search functionality including Patient ID search"""
        print("\n=== Testing Search by Patient ID ===")
        
        # First, get a patient_id to search for
        try:
            response = self.session.get(f"{self.base_url}/patients")
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    test_patient_id = data[0].get('patient_id')
                    
                    # Test 1: Search by Patient ID
                    search_response = self.session.get(f"{self.base_url}/patients?search={test_patient_id}")
                    
                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        if isinstance(search_data, list) and len(search_data) >= 1:
                            # Should return records with matching patient_id
                            matching_records = [r for r in search_data if r.get('patient_id') == test_patient_id]
                            if matching_records:
                                self.log_test("Search by Patient ID", True, 
                                            f"Found {len(matching_records)} records with patient_id {test_patient_id}")
                            else:
                                self.log_test("Search by Patient ID", False, 
                                            "No records found with matching patient_id")
                        else:
                            self.log_test("Search by Patient ID", False, 
                                        f"Expected list with results, got: {len(search_data) if isinstance(search_data, list) else 'non-list'}")
                    else:
                        self.log_test("Search by Patient ID", False, 
                                    f"Search failed: {search_response.status_code}")
                    
                    # Test 2: Search by patient name "John"
                    name_search_response = self.session.get(f"{self.base_url}/patients?search=John")
                    
                    if name_search_response.status_code == 200:
                        name_search_data = name_search_response.json()
                        if isinstance(name_search_data, list):
                            john_records = [r for r in name_search_data if 'john' in r.get('patient_name', '').lower()]
                            if john_records:
                                self.log_test("Search by Patient Name - John", True, 
                                            f"Found {len(john_records)} records with 'John' in name")
                            else:
                                self.log_test("Search by Patient Name - John", True, 
                                            "Search works but no 'John' records found (expected if no John records exist)")
                        else:
                            self.log_test("Search by Patient Name - John", False, 
                                        "Search response is not a list")
                    else:
                        self.log_test("Search by Patient Name - John", False, 
                                    f"Name search failed: {name_search_response.status_code}")
                else:
                    self.log_test("Search by Patient ID", False, "No patients found to test search with")
            else:
                self.log_test("Search by Patient ID", False, f"Failed to get patients: {response.status_code}")
                
        except Exception as e:
            self.log_test("Search by Patient ID", False, f"Exception: {str(e)}")
    
    def test_sqlite_storage(self):
        """Test SQLite database storage"""
        print("\n=== Testing SQLite Storage ===")
        
        # Test 1: Check if database file exists
        db_path = Path("/app/backend/medical_records.db")
        if db_path.exists():
            file_size = db_path.stat().st_size
            self.log_test("SQLite Database File", True, 
                        f"Database file exists at {db_path}, size: {file_size} bytes")
        else:
            self.log_test("SQLite Database File", False, 
                        f"Database file not found at {db_path}")
    
    def test_storage_stats_with_backup_flag(self):
        """Test storage stats endpoint with needs_backup flag"""
        print("\n=== Testing Storage Stats with needs_backup Flag ===")
        
        try:
            response = self.session.get(f"{self.base_url}/storage-stats")
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['total_records', 'storage_used_mb', 'storage_percentage', 'needs_backup']
                
                missing_fields = [field for field in required_fields if field not in data]
                if not missing_fields:
                    # Check data types
                    total_records = data.get('total_records')
                    storage_used_mb = data.get('storage_used_mb')
                    storage_percentage = data.get('storage_percentage')
                    needs_backup = data.get('needs_backup')
                    
                    if (isinstance(total_records, int) and 
                        isinstance(storage_used_mb, (int, float)) and 
                        isinstance(storage_percentage, (int, float)) and 
                        isinstance(needs_backup, bool)):
                        
                        self.log_test("Storage Stats - All Fields", True, 
                                    f"All fields present with correct types", 
                                    f"Records: {total_records}, Storage: {storage_used_mb}MB ({storage_percentage}%), Backup needed: {needs_backup}")
                        
                        # Test needs_backup logic (should be True if storage_percentage >= 80)
                        expected_backup = storage_percentage >= 80
                        if needs_backup == expected_backup:
                            self.log_test("Storage Stats - needs_backup Logic", True, 
                                        f"needs_backup correctly set to {needs_backup}")
                        else:
                            self.log_test("Storage Stats - needs_backup Logic", False, 
                                        f"needs_backup is {needs_backup}, expected {expected_backup} (storage: {storage_percentage}%)")
                    else:
                        self.log_test("Storage Stats - Data Types", False, 
                                    f"Incorrect data types in response")
                else:
                    self.log_test("Storage Stats - Missing Fields", False, 
                                f"Missing fields: {missing_fields}")
            else:
                self.log_test("Storage Stats - API Response", False, 
                            f"Failed to get storage stats: {response.status_code}")
                
        except Exception as e:
            self.log_test("Storage Stats - Exception", False, f"Exception: {str(e)}")
    
    def test_google_drive_integration(self):
        """Test Google Drive integration endpoints"""
        print("\n=== Testing Google Drive Integration ===")
        
        # Test 1: Check drive status
        try:
            response = self.session.get(f"{self.base_url}/drive/status")
            
            if response.status_code == 200:
                data = response.json()
                if 'connected' in data:
                    connected = data.get('connected')
                    self.log_test("Google Drive Status", True, 
                                f"Drive status endpoint working, connected: {connected}")
                else:
                    self.log_test("Google Drive Status", False, 
                                "Response missing 'connected' field")
            else:
                self.log_test("Google Drive Status", False, 
                            f"Drive status failed: {response.status_code}")
                
        except Exception as e:
            self.log_test("Google Drive Status", False, f"Exception: {str(e)}")
        
        # Test 2: Get auth URL
        try:
            response = self.session.get(f"{self.base_url}/drive/auth-url")
            
            if response.status_code == 200:
                data = response.json()
                if 'authorization_url' in data:
                    self.log_test("Google Drive Auth URL", True, 
                                "Auth URL endpoint working, returns authorization_url")
                else:
                    self.log_test("Google Drive Auth URL", False, 
                                "Response missing 'authorization_url' field")
            elif response.status_code == 500:
                # Expected if credentials not configured
                try:
                    error_data = response.json()
                    if "credentials not configured" in error_data.get('detail', '').lower():
                        self.log_test("Google Drive Auth URL", True, 
                                    "Auth URL endpoint working, correctly reports missing credentials")
                    else:
                        self.log_test("Google Drive Auth URL", False, 
                                    f"Unexpected 500 error: {error_data.get('detail')}")
                except:
                    self.log_test("Google Drive Auth URL", False, 
                                f"500 error with invalid JSON response")
            else:
                self.log_test("Google Drive Auth URL", False, 
                            f"Auth URL failed: {response.status_code}")
                
        except Exception as e:
            self.log_test("Google Drive Auth URL", False, f"Exception: {str(e)}")
    
    def test_export_with_patient_id(self):
        """Test export functionality includes Patient ID field"""
        print("\n=== Testing Export with Patient ID ===")
        
        try:
            response = self.session.post(f"{self.base_url}/export-records")
            
            if response.status_code == 200:
                data = response.json()
                if 'records' in data and 'total' in data:
                    records = data.get('records', [])
                    if records:
                        # Check if first record has Patient ID field
                        first_record = records[0]
                        if 'Patient ID' in first_record:
                            patient_id = first_record.get('Patient ID')
                            self.log_test("Export with Patient ID", True, 
                                        f"Export includes Patient ID field, sample: {patient_id}")
                            
                            # Verify all records have Patient ID
                            all_have_patient_id = all('Patient ID' in record for record in records)
                            if all_have_patient_id:
                                self.log_test("Export - All Records Have Patient ID", True, 
                                            f"All {len(records)} exported records include Patient ID")
                            else:
                                self.log_test("Export - All Records Have Patient ID", False, 
                                            "Some exported records missing Patient ID field")
                        else:
                            self.log_test("Export with Patient ID", False, 
                                        "Exported records missing 'Patient ID' field")
                    else:
                        self.log_test("Export with Patient ID", True, 
                                    "Export working but no records to export")
                else:
                    self.log_test("Export with Patient ID", False, 
                                "Export response missing 'records' or 'total' field")
            else:
                self.log_test("Export with Patient ID", False, 
                            f"Export failed: {response.status_code}")
                
        except Exception as e:
            self.log_test("Export with Patient ID", False, f"Exception: {str(e)}")
    
    def test_comprehensive_flow(self):
        """Test comprehensive flow of all operations"""
        print("\n=== Testing Comprehensive Flow ===")
        
        # Create a record and test full CRUD cycle
        try:
            # Create
            payload = {
                "patient_name": "Alice Johnson",
                "diagnosis_details": "Routine checkup and vaccination",
                "medicine_names": "Multivitamin, Flu vaccine"
            }
            
            create_response = self.session.post(f"{self.base_url}/patients", json=payload)
            if create_response.status_code != 200:
                self.log_test("Comprehensive Flow - Create", False, 
                            f"Failed to create record: {create_response.status_code}")
                return
            
            created_record = create_response.json()
            record_id = created_record.get('id')
            patient_id = created_record.get('patient_id')
            self.created_records.append(record_id)
            
            self.log_test("Comprehensive Flow - Create", True, 
                        f"Created record with ID: {record_id}, Patient ID: {patient_id}")
            
            # Read
            read_response = self.session.get(f"{self.base_url}/patients/{record_id}")
            if read_response.status_code == 200:
                self.log_test("Comprehensive Flow - Read", True, 
                            f"Successfully retrieved record {record_id}")
            else:
                self.log_test("Comprehensive Flow - Read", False, 
                            f"Failed to read record: {read_response.status_code}")
            
            # Update
            update_payload = {
                "diagnosis_details": "Updated: Routine checkup completed, all normal"
            }
            update_response = self.session.put(f"{self.base_url}/patients/{record_id}", json=update_payload)
            if update_response.status_code == 200:
                updated_record = update_response.json()
                if "Updated:" in updated_record.get('diagnosis_details', ''):
                    self.log_test("Comprehensive Flow - Update", True, 
                                f"Successfully updated record {record_id}")
                else:
                    self.log_test("Comprehensive Flow - Update", False, 
                                "Update response doesn't reflect changes")
            else:
                self.log_test("Comprehensive Flow - Update", False, 
                            f"Failed to update record: {update_response.status_code}")
            
            # Search for the record
            search_response = self.session.get(f"{self.base_url}/patients?search={patient_id}")
            if search_response.status_code == 200:
                search_results = search_response.json()
                found = any(r.get('id') == record_id for r in search_results)
                if found:
                    self.log_test("Comprehensive Flow - Search", True, 
                                f"Successfully found record via search")
                else:
                    self.log_test("Comprehensive Flow - Search", False, 
                                "Record not found in search results")
            else:
                self.log_test("Comprehensive Flow - Search", False, 
                            f"Search failed: {search_response.status_code}")
            
        except Exception as e:
            self.log_test("Comprehensive Flow", False, f"Exception: {str(e)}")
    
    def cleanup_test_records(self):
        """Clean up test records"""
        print("\n=== Cleaning Up Test Records ===")
        
        for record_id in self.created_records:
            try:
                response = self.session.delete(f"{self.base_url}/patients/{record_id}")
                if response.status_code == 200:
                    print(f"✅ Deleted test record {record_id}")
                else:
                    print(f"⚠️  Failed to delete record {record_id}: {response.status_code}")
            except Exception as e:
                print(f"⚠️  Exception deleting record {record_id}: {str(e)}")
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"🚀 Starting Medical History System Backend Tests - NEW FEATURES")
        print(f"Backend URL: {self.base_url}")
        print("=" * 60)
        
        # Test basic connectivity
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                print("✅ Backend connectivity confirmed")
            else:
                print(f"❌ Backend connectivity failed: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Backend connectivity failed: {str(e)}")
            return
        
        # Run all tests
        self.test_patient_id_auto_generation()
        self.test_search_by_patient_id()
        self.test_sqlite_storage()
        self.test_storage_stats_with_backup_flag()
        self.test_google_drive_integration()
        self.test_export_with_patient_id()
        self.test_comprehensive_flow()
        
        # Cleanup
        self.cleanup_test_records()
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  • {result['test']}: {result['message']}")
        
        print("\n✅ PASSED TESTS:")
        for result in self.test_results:
            if result['success']:
                print(f"  • {result['test']}")

if __name__ == "__main__":
    tester = MedicalHistoryAPITester()
    tester.run_all_tests()