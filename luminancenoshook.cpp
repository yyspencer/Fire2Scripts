#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <limits>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <set>
#include <utility>
#include <limits>

using namespace std;
namespace fs = filesystem;
typedef long long ll;
typedef pair<ll, ll> pll;
#define pub push_back
#define mp make_pair
#define pob pop_back
#define X first
#define Y second
const ll INF = 0x3f3f3f3f3f3f3f3f;

// Function to trim whitespace from a string
string trim(const string& str) {
    string trimmed = str;
    trimmed.erase(trimmed.begin(), find_if(trimmed.begin(), trimmed.end(), [](unsigned char ch) {
        return !isspace(ch);
    }));
    trimmed.erase(find_if(trimmed.rbegin(), trimmed.rend(), [](unsigned char ch) {
        return !isspace(ch);
    }).base(), trimmed.end());
    return trimmed;
}

// Function to check if a file has a .csv extension
bool isCSVFile(const fs::path& filePath) {
    return filePath.extension() == ".csv";
}

// Function to load CSV file into a 2D vector
vector<vector<string>> loadCSV(const string& filePath) {
    vector<vector<string>> data;
    ifstream file(filePath);
    if (!file.is_open()) {
        cerr << "Error: Could not open " << filePath << endl;
        return {};
    }

    string line;
    while (getline(file, line)) {
        stringstream ss(line);
        vector<string> row;
        string cell;
        while (getline(ss, cell, ',')) {
            row.pub(cell);
        }
        data.pub(row);
    }
    file.close();
    return data;
}

// Function to find the columns that contain "leftPupil" (and "rightPupil" if needed)
pair<int, int> findPupilColumns(const vector<string>& headerRow) {
    int leftPupilCol = -1, rightPupilCol = -1;
    for (size_t i = 0; i < headerRow.size(); i++) {
        string trimmedCell = trim(headerRow[i]);
        if (trimmedCell.find("leftPupil") != string::npos) {
            leftPupilCol = i;
        }
        if (trimmedCell.find("rightPupil") != string::npos) {
            rightPupilCol = i;
        }
    }
    return {leftPupilCol, rightPupilCol};
}

// Function to find the row index that contains the "0.2 seconds" tag
int findEventRow(const vector<vector<string>>& data) {
    for (size_t i = 1; i < data.size(); i++) { // start after header
        for (const string& cell : data[i]) {
            if (cell.find("0.2 seconds") != string::npos) {
                return i;  // Return the first occurrence
            }
        }
    }
    return -1;  // Not found
}

int main() {
    ios_base::sync_with_stdio(0);
    cin.tie(0);

    string path = ".";
    fs::path noshookFolder = fs::path(path) / "noshook";
    fs::path luminanceFolder = fs::path(path) / "luminance";

    // Create the luminance folder if it doesn't exist
    if (!fs::exists(luminanceFolder)) {
        fs::create_directory(luminanceFolder);
    }

    cout << "Scanning CSV files in the noshook folder..." << endl;
    if (!fs::exists(noshookFolder) || !fs::is_directory(noshookFolder)) {
        cerr << "Error: 'noshook' folder does not exist!" << endl;
        return 1;
    }

    // Process each CSV file in the noshook folder
    for (const auto& entry : fs::directory_iterator(noshookFolder)) {
        if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
            string fileName = entry.path().filename().string();
            // The file index is the first 5 characters of the filename
            string fileIndex = fileName.substr(0, 5);
            cout << "Extracting luminance level of file " << fileIndex << endl;

            // Load CSV file data
            vector<vector<string>> data = loadCSV(entry.path().string());
            if (data.empty()) {
                cout << "Index " << fileIndex << " -> ERROR: Could not load CSV ❌" << endl;
                continue;
            }

            // Find the left pupil column; luminance is in the column immediately before leftPupil
            pair<int, int> pupilColumns = findPupilColumns(data[0]);
            if (pupilColumns.first == -1) {
                cout << "Index " << fileIndex << " -> ERROR: 'leftPupil' column not found ❌" << endl;
                continue;
            }
            int luminanceCol = pupilColumns.first - 1;

            // Locate the event row (the one containing "0.2 seconds")
            int eventRow = findEventRow(data);
            if (eventRow == -1) {
                cout << "Index " << fileIndex << " -> ERROR: '0.2 seconds' tag not found ❌" << endl;
                continue;
            }

            // Extract the time at the event row (from column 0) and calculate the estimated event start time
            double beforeTime = 0.0;
            try {
                beforeTime = stod(data[eventRow][0]);
            } catch (...) {
                cout << "Index " << fileIndex << " -> ERROR: Invalid time value in event row ❌" << endl;
                continue;
            }
            double eventTime = beforeTime + 0.229;

            vector<double> luminanceBefore;
            vector<double> luminanceAfter;

            // Iterate through all data rows (skip header)
            for (size_t i = 1; i < data.size(); i++) {
                if (data[i].size() <= (unsigned)luminanceCol)
                    continue;
                double timeValue, luminance;
                try {
                    timeValue = stod(data[i][0]);
                    luminance = stod(data[i][luminanceCol]);
                } catch (...) {
                    continue;
                }
                // Exclude invalid luminance values
                if (luminance == -1)
                    continue;

                // Collect luminance values for the before window: 5 seconds before the "0.2 seconds" tag
                if (timeValue >= (beforeTime - 5.0) && timeValue <= beforeTime) {
                    luminanceBefore.pub(luminance);
                }
                // Collect luminance values for the after window: 5 seconds after the estimated event time
                if (timeValue >= eventTime && timeValue <= (eventTime + 5.0)) {
                    luminanceAfter.pub(luminance);
                }
            }

            // Build the output file name: index+luminance.txt in the luminance folder
            string outFileName = (luminanceFolder / (fileIndex + "luminance.txt")).string();
            ofstream outFile(outFileName);
            if (!outFile) {
                cerr << "Error: Could not open file " << outFileName << " for writing." << endl;
                continue;
            }

            // Write before-window luminance values (one per line)
            for (double val : luminanceBefore) {
                outFile << val << "\n";
            }
            // Write an empty line to separate the two windows
            outFile << "\n";
            // Write after-window luminance values (one per line)
            for (double val : luminanceAfter) {
                outFile << val << "\n";
            }
            outFile.close();
            cout << "Finished processing file " << fileIndex << endl;
        }
    }

    cout << "Luminance extraction complete." << endl;
    return 0;
}