#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <algorithm> // For transforming text to lowercase
#include <iomanip>   // For setting decimal precision

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

// Function to convert a string to lowercase
string toLowerCase(string str) {
    transform(str.begin(), str.end(), str.begin(), ::tolower);
    return str;
}

// Struct to store calibration search results for an index
struct CalibrationResult {
    string index;
    bool hasStart = false;
    bool hasFinish = false;
    int startRow = -1, startCol = -1;
    int finishRow = -1, finishCol = -1;
    fs::path filePath;  // Store file path for moving
};

// Function to search for "start calibration" and "finished calibration" in a CSV file
CalibrationResult searchCalibrationKeywords(const fs::path& filePath) {
    ifstream file(filePath);
    CalibrationResult result;
    result.index = extractIndex(filePath.filename().string());
    result.filePath = filePath;

    if (!file.is_open()) {
        cerr << "Error: Could not open " << filePath << endl;
        return result;
    }

    string line;
    int rowNum = 0; // Row counter

    while (getline(file, line)) {
        stringstream ss(line);
        string cell;
        int colNum = 0; // Column counter

        while (getline(ss, cell, ',')) {
            string lowerCell = toLowerCase(cell); // Convert cell text to lowercase

            if (lowerCell.find("start calibration") != string::npos && !result.hasStart) {
                result.hasStart = true;
                result.startRow = rowNum;
                result.startCol = colNum;
            }
            if (lowerCell.find("finished calibration") != string::npos && !result.hasFinish) {
                result.hasFinish = true;
                result.finishRow = rowNum;
                result.finishCol = colNum;
            }
            colNum++;
        }

        rowNum++;
    }

    file.close();
    return result;
}

int main() {
    string path = "evolab"; // Folder containing the CSV files
    fs::path completeFolder = fs::path(path) / "complete";

    if (!fs::exists(path) || !fs::is_directory(path)) {
        cerr << "Error: 'evolab' folder does not exist!" << endl;
        return 1;
    }

    // Create "complete" folder if it does not exist
    if (!fs::exists(completeFolder)) {
        fs::create_directory(completeFolder);
        cout << "Created 'complete' folder inside 'evolab'.\n";
    }

    cout << "\n==== Evolab Calibration Search ====\n";

    vector<CalibrationResult> results;
    int countBoth = 0, countOnlyStart = 0, countOnlyFinish = 0, countNone = 0;

    for (const auto& entry : fs::directory_iterator(path)) {
        if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
            CalibrationResult result = searchCalibrationKeywords(entry.path());
            results.push_back(result);

            // Determine category
            if (result.hasStart && result.hasFinish) {
                countBoth++;

                // Move file to "complete" folder
                fs::path newFilePath = completeFolder / entry.path().filename();
                fs::rename(entry.path(), newFilePath);
                cout << "Moved " << entry.path().filename().string() << " to 'complete' folder.\n";

            } else if (result.hasStart) {
                countOnlyStart++;
            } else if (result.hasFinish) {
                countOnlyFinish++;
            } else {
                countNone++;
            }

            // Print result for this file
            cout << "Index: " << result.index << ", ";
            if (result.hasStart) {
                cout << "Start Calibration: Yes (Row " << result.startRow << ", Col " << result.startCol << "), ";
            } else {
                cout << "Start Calibration: No, ";
            }
            if (result.hasFinish) {
                cout << "Finished Calibration: Yes (Row " << result.finishRow << ", Col " << result.finishCol << ")";
            } else {
                cout << "Finished Calibration: No";
            }
            cout << endl;
        }
    }

    int totalFiles = results.size();

    // Compute percentages
    double percentBoth = (totalFiles > 0) ? (countBoth * 100.0 / totalFiles) : 0.0;
    double percentOnlyStart = (totalFiles > 0) ? (countOnlyStart * 100.0 / totalFiles) : 0.0;
    double percentOnlyFinish = (totalFiles > 0) ? (countOnlyFinish * 100.0 / totalFiles) : 0.0;
    double percentNone = (totalFiles > 0) ? (countNone * 100.0 / totalFiles) : 0.0;

    // Print summary statistics
    cout << "\n==== Summary Statistics ====\n";
    cout << fixed << setprecision(2);
    cout << "Total CSV Files: " << totalFiles << "\n";
    cout << "Both 'Start' & 'Finished' Calibration: " << countBoth << " (" << percentBoth << "%)\n";
    cout << "Only 'Start' Calibration: " << countOnlyStart << " (" << percentOnlyStart << "%)\n";
    cout << "Only 'Finished' Calibration: " << countOnlyFinish << " (" << percentOnlyFinish << "%)\n";
    cout << "No Calibration Keywords Found: " << countNone << " (" << percentNone << "%)\n";

    cout << "\nProcessing complete.\n";
    return 0;
}