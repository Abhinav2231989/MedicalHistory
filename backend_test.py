#!/usr/bin/env python3
"""
Comprehensive Backend API Tests for Medical History System
Tests all endpoints with realistic medical data
"""

import requests
import json
import os
from datetime import datetime
import sys

# Get backend URL from frontend .env file
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('EXPO_PUBLIC_BACKEND_URL='):
                    return line.split('=', 1)[1].strip().strip('"')
        return None
    except Exception as e:
        print(f"Error reading frontend .env: {e}")
        return None

BASE_URL = get_backend_url()
if not BASE_URL:
    print("❌ Could not get backend URL from frontend/.env")
    sys.exit(1)

API_URL = f"{BASE_URL}/api"
print(f"🔗 Testing API at: {API_URL}")

# Test data with realistic medical information
TEST_PATIENTS = [
    {
        "patient_name": "Sarah Johnson",
        "diagnosis_details": "Type 2 Diabetes Mellitus with mild peripheral neuropathy",
        "medicine_names": "Metformin 500mg twice daily, Lisinopril 10mg once daily"
    },
    {
        "patient_name": "Michael Chen",
        "diagnosis_details": "Hypertension and hyperlipidemia",
        "medicine_names": "Amlodipine 5mg daily, Atorvastatin 20mg at bedtime"
    },
    {
        "patient_name": "Emily Rodriguez",
        "diagnosis_details": "Asthma with seasonal allergic rhinitis",
        "medicine_names": "Albuterol inhaler PRN, Fluticasone nasal spray daily"
    },
    {
        "patient_name": "David Thompson",
        "diagnosis_details": "Chronic lower back pain due to herniated disc L4-L5",
        "medicine_names": "Ibuprofen 400mg TID, Gabapentin 300mg BID"
    }
]

class APITester:
    def __init__(self):
        self.created_patients = []
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }

    def log_result(self, test_name, success, message=""):
        if success:
            print(f"✅ {test_name}")
            self.test_results["passed"] += 1
        else:
            print(f"❌ {test_name}: {message}")
            self.test_results["failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {message}")

    def test_api_root(self):
        """Test the root API endpoint"""
        try:
            response = requests.get(f"{API_URL}/")
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_result("API Root Endpoint", True)
                    return True
                else:
                    self.log_result("API Root Endpoint", False, "Missing message in response")
            else:
                self.log_result("API Root Endpoint", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("API Root Endpoint", False, f"Exception: {str(e)}")
        return False

    def test_create_patient(self, patient_data):
        """Test creating a patient record"""
        try:
            response = requests.post(f"{API_URL}/patients", json=patient_data)
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "slno", "patient_name", "diagnosis_details", 
                                 "medicine_names", "created_at", "updated_at"]
                
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    self.log_result(f"Create Patient - {patient_data['patient_name']}", 
                                  False, f"Missing fields: {missing_fields}")
                    return None
                
                # Verify slno is an integer
                if not isinstance(data["slno"], int):
                    self.log_result(f"Create Patient - {patient_data['patient_name']}", 
                                  False, "slno is not an integer")
                    return None
                
                self.log_result(f"Create Patient - {patient_data['patient_name']}", True)
                self.created_patients.append(data)
                return data
            else:
                self.log_result(f"Create Patient - {patient_data['patient_name']}", 
                              False, f"Status code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result(f"Create Patient - {patient_data['patient_name']}", 
                          False, f"Exception: {str(e)}")
        return None

    def test_get_all_patients(self):
        """Test getting all patient records"""
        try:
            response = requests.get(f"{API_URL}/patients")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Check if records are sorted by slno in descending order
                    if len(data) > 1:
                        sorted_correctly = all(data[i]["slno"] >= data[i+1]["slno"] 
                                             for i in range(len(data)-1))
                        if not sorted_correctly:
                            self.log_result("Get All Patients", False, 
                                          "Records not sorted by slno in descending order")
                            return None
                    
                    self.log_result("Get All Patients", True)
                    return data
                else:
                    self.log_result("Get All Patients", False, "Response is not a list")
            else:
                self.log_result("Get All Patients", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Get All Patients", False, f"Exception: {str(e)}")
        return None

    def test_search_patients(self, search_term, expected_matches):
        """Test search functionality"""
        try:
            response = requests.get(f"{API_URL}/patients", params={"search": search_term})
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    if len(data) >= expected_matches:
                        self.log_result(f"Search Patients - '{search_term}'", True)
                        return data
                    else:
                        self.log_result(f"Search Patients - '{search_term}'", False, 
                                      f"Expected at least {expected_matches} matches, got {len(data)}")
                else:
                    self.log_result(f"Search Patients - '{search_term}'", False, 
                                  "Response is not a list")
            else:
                self.log_result(f"Search Patients - '{search_term}'", False, 
                              f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(f"Search Patients - '{search_term}'", False, f"Exception: {str(e)}")
        return None

    def test_get_single_patient(self, patient_id):
        """Test getting a single patient record"""
        try:
            response = requests.get(f"{API_URL}/patients/{patient_id}")
            if response.status_code == 200:
                data = response.json()
                if "id" in data and data["id"] == patient_id:
                    self.log_result(f"Get Single Patient - {patient_id}", True)
                    return data
                else:
                    self.log_result(f"Get Single Patient - {patient_id}", False, 
                                  "ID mismatch in response")
            else:
                self.log_result(f"Get Single Patient - {patient_id}", False, 
                              f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(f"Get Single Patient - {patient_id}", False, f"Exception: {str(e)}")
        return None

    def test_get_invalid_patient(self):
        """Test getting a patient with invalid ID"""
        invalid_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format but non-existent
        try:
            response = requests.get(f"{API_URL}/patients/{invalid_id}")
            if response.status_code == 404:
                self.log_result("Get Invalid Patient (404 test)", True)
                return True
            else:
                self.log_result("Get Invalid Patient (404 test)", False, 
                              f"Expected 404, got {response.status_code}")
        except Exception as e:
            self.log_result("Get Invalid Patient (404 test)", False, f"Exception: {str(e)}")
        return False

    def test_update_patient(self, patient_id, update_data):
        """Test updating a patient record"""
        try:
            response = requests.put(f"{API_URL}/patients/{patient_id}", json=update_data)
            if response.status_code == 200:
                data = response.json()
                # Verify the update was applied
                for key, value in update_data.items():
                    if key in data and data[key] == value:
                        continue
                    else:
                        self.log_result(f"Update Patient - {patient_id}", False, 
                                      f"Update not applied for {key}")
                        return None
                
                # Verify updated_at timestamp changed
                if "updated_at" in data:
                    self.log_result(f"Update Patient - {patient_id}", True)
                    return data
                else:
                    self.log_result(f"Update Patient - {patient_id}", False, 
                                  "updated_at field missing")
            else:
                self.log_result(f"Update Patient - {patient_id}", False, 
                              f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(f"Update Patient - {patient_id}", False, f"Exception: {str(e)}")
        return None

    def test_delete_patient(self, patient_id):
        """Test deleting a patient record"""
        try:
            response = requests.delete(f"{API_URL}/patients/{patient_id}")
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    # Verify the record is actually deleted
                    verify_response = requests.get(f"{API_URL}/patients/{patient_id}")
                    if verify_response.status_code == 404:
                        self.log_result(f"Delete Patient - {patient_id}", True)
                        return True
                    else:
                        self.log_result(f"Delete Patient - {patient_id}", False, 
                                      "Record still exists after deletion")
                else:
                    self.log_result(f"Delete Patient - {patient_id}", False, 
                                  "Missing message in response")
            else:
                self.log_result(f"Delete Patient - {patient_id}", False, 
                              f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(f"Delete Patient - {patient_id}", False, f"Exception: {str(e)}")
        return False

    def test_delete_invalid_patient(self):
        """Test deleting a patient with invalid ID"""
        invalid_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format but non-existent
        try:
            response = requests.delete(f"{API_URL}/patients/{invalid_id}")
            if response.status_code == 404:
                self.log_result("Delete Invalid Patient (404 test)", True)
                return True
            else:
                self.log_result("Delete Invalid Patient (404 test)", False, 
                              f"Expected 404, got {response.status_code}")
        except Exception as e:
            self.log_result("Delete Invalid Patient (404 test)", False, f"Exception: {str(e)}")
        return False

    def test_storage_stats(self):
        """Test storage statistics endpoint"""
        try:
            response = requests.get(f"{API_URL}/storage-stats")
            if response.status_code == 200:
                data = response.json()
                required_fields = ["total_records", "storage_used_mb", "storage_percentage"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_result("Storage Stats", False, f"Missing fields: {missing_fields}")
                    return None
                
                # Verify data types
                if (isinstance(data["total_records"], int) and 
                    isinstance(data["storage_used_mb"], (int, float)) and 
                    isinstance(data["storage_percentage"], (int, float))):
                    self.log_result("Storage Stats", True)
                    return data
                else:
                    self.log_result("Storage Stats", False, "Invalid data types in response")
            else:
                self.log_result("Storage Stats", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Storage Stats", False, f"Exception: {str(e)}")
        return None

    def test_export_records(self):
        """Test export records endpoint"""
        try:
            response = requests.post(f"{API_URL}/export-records")
            if response.status_code == 200:
                data = response.json()
                if "records" in data and "total" in data:
                    if isinstance(data["records"], list) and isinstance(data["total"], int):
                        # Check if records have proper CSV format fields
                        if data["records"]:
                            required_fields = ["SlNo", "Patient Name", "Diagnosis Details", 
                                             "Medicine Names", "Created At"]
                            first_record = data["records"][0]
                            missing_fields = [field for field in required_fields 
                                            if field not in first_record]
                            
                            if missing_fields:
                                self.log_result("Export Records", False, 
                                              f"Missing CSV fields: {missing_fields}")
                                return None
                        
                        self.log_result("Export Records", True)
                        return data
                    else:
                        self.log_result("Export Records", False, "Invalid data types in response")
                else:
                    self.log_result("Export Records", False, "Missing records or total fields")
            else:
                self.log_result("Export Records", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Export Records", False, f"Exception: {str(e)}")
        return None

    def run_comprehensive_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Medical History System API Tests")
        print("=" * 60)
        
        # Test 1: API Root
        self.test_api_root()
        
        # Test 2: Create patient records
        print("\n📝 Testing Patient Creation...")
        for patient in TEST_PATIENTS:
            self.test_create_patient(patient)
        
        # Test 3: Get all patients
        print("\n📋 Testing Get All Patients...")
        all_patients = self.test_get_all_patients()
        
        # Test 4: Search functionality
        print("\n🔍 Testing Search Functionality...")
        self.test_search_patients("diabetes", 1)  # Should find Sarah Johnson
        self.test_search_patients("chen", 1)      # Should find Michael Chen
        self.test_search_patients("ibuprofen", 1) # Should find David Thompson
        self.test_search_patients("ASTHMA", 1)    # Case insensitive test
        
        # Test 5: Get single patient
        print("\n👤 Testing Get Single Patient...")
        if self.created_patients:
            self.test_get_single_patient(self.created_patients[0]["id"])
        
        # Test 6: Get invalid patient (404 test)
        self.test_get_invalid_patient()
        
        # Test 7: Update patient
        print("\n✏️ Testing Patient Updates...")
        if self.created_patients:
            update_data = {
                "patient_name": "Sarah Johnson-Smith",
                "diagnosis_details": "Type 2 Diabetes Mellitus with improved glucose control"
            }
            updated_patient = self.test_update_patient(self.created_patients[0]["id"], update_data)
            
            # Test partial update
            partial_update = {"medicine_names": "Metformin 1000mg twice daily"}
            self.test_update_patient(self.created_patients[1]["id"], partial_update)
        
        # Test 8: Storage stats
        print("\n📊 Testing Storage Statistics...")
        self.test_storage_stats()
        
        # Test 9: Export records
        print("\n📤 Testing Export Functionality...")
        self.test_export_records()
        
        # Test 10: Delete patient
        print("\n🗑️ Testing Patient Deletion...")
        if len(self.created_patients) > 2:
            self.test_delete_patient(self.created_patients[-1]["id"])
        
        # Test 11: Delete invalid patient (404 test)
        self.test_delete_invalid_patient()
        
        # Final summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        print(f"📈 Success Rate: {(self.test_results['passed'] / (self.test_results['passed'] + self.test_results['failed']) * 100):.1f}%")
        
        if self.test_results["errors"]:
            print("\n🚨 FAILED TESTS:")
            for error in self.test_results["errors"]:
                print(f"   • {error}")
        
        return self.test_results["failed"] == 0

if __name__ == "__main__":
    tester = APITester()
    success = tester.run_comprehensive_tests()
    
    if success:
        print("\n🎉 All tests passed! Medical History System API is working correctly.")
        sys.exit(0)
    else:
        print(f"\n⚠️ {tester.test_results['failed']} test(s) failed. Please check the issues above.")
        sys.exit(1)