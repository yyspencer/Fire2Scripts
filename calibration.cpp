#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <set>
#include <map>

using namespace std;
namespace fs = filesystem;

// Function to check if a file has a .csv extension
bool isCSVFile(const fs::path& filePath) {
    return filePath.extension() == ".csv";
}

// Function to extract the first 5 characters as an index
string extractIndex(const string& fileName) {
    return fileName.substr(0, 5); // First 5 characters represent the index
}

int main() {
    string path = "."; // Default to current directory
    fs::path evolabFolder = fs::path(path) / "evolab";
    fs::path shookFolder = fs::path(path) / "shook";
    fs::path noshookFolder = fs::path(path) / "noshook";

    set<string> evolabIndices;   // Store indices of files in evolab folder
    set<string> shookIndices;    // Store indices of files in shook folder
    set<string> noshookIndices;  // Store indices of files in noshook folder
    set<string> allIndices;      // Store all unique indices

    cout << "Scanning CSV files in evolab, shook, and noshook folders..." << endl;

    // Scan evolab folder
    if (fs::exists(evolabFolder) && fs::is_directory(evolabFolder)) {
        for (const auto& entry : fs::directory_iterator(evolabFolder)) {
            if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
                string fileIndex = extractIndex(entry.path().filename().string());
                evolabIndices.insert(fileIndex);
                allIndices.insert(fileIndex);
            }
        }
    }

    // Scan shook folder
    if (fs::exists(shookFolder) && fs::is_directory(shookFolder)) {
        for (const auto& entry : fs::directory_iterator(shookFolder)) {
            if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
                string fileIndex = extractIndex(entry.path().filename().string());
                shookIndices.insert(fileIndex);
                allIndices.insert(fileIndex);
            }
        }
    }

    // Scan noshook folder
    if (fs::exists(noshookFolder) && fs::is_directory(noshookFolder)) {
        for (const auto& entry : fs::directory_iterator(noshookFolder)) {
            if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
                string fileIndex = extractIndex(entry.path().filename().string());
                noshookIndices.insert(fileIndex);
                allIndices.insert(fileIndex);
            }
        }
    }

    // Save comparison results to a file
    ofstream comparisonFile("evolab_shook_noshook_comparison.txt");
    if (comparisonFile.is_open()) {
        comparisonFile << "Index | Evolab Exists? | Exists in Shook/Noshook?\n";
        comparisonFile << "---------------------------------------------\n";
        for (const auto& index : allIndices) {
            string evolabStatus = evolabIndices.count(index) ? "YES" : "NO";
            string existsInShookNoshook = (shookIndices.count(index) || noshookIndices.count(index)) ? "YES" : "NO";
            comparisonFile << index << " | " << evolabStatus << " | " << existsInShookNoshook << endl;
        }
        comparisonFile.close();
        cout << "Saved comparison results to evolab_shook_noshook_comparison.txt" << endl;
    } else {
        cerr << "Error: Could not create evolab_shook_noshook_comparison.txt" << endl;
    }

    cout << "\nProcessing complete." << endl;
    return 0;
}