//gets all datapoints mapped to a single txt file for shook files
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

// Function to find the columns that contain "leftPupil" and "rightPupil"
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

// Function to find the row indices for the "0.2 seconds" and "shook" events
pair<int, int> findEventRows(const vector<vector<string>>& data, int eventColumn) {
    int rowFor02 = -1, rowForShook = -1;
    for (size_t i = 1; i < data.size(); i++) { // skip header
        if (data[i].size() <= eventColumn) continue;
        string eventColumnValue = data[i][eventColumn];
        if (eventColumnValue.find("0.2 seconds") != string::npos && rowFor02 == -1) {
            rowFor02 = i;
        }
        if (eventColumnValue.find("shook") != string::npos && rowForShook == -1) {
            rowForShook = i;
        }
        if (rowFor02 != -1 && rowForShook != -1) break;
    }
    return {rowFor02, rowForShook};
}

int main() {
    ios_base::sync_with_stdio(0);
    cin.tie(0);

    // Define folder paths:
    string path = ".";
    fs::path shookFolder = fs::path(path) / "shook";
    fs::path pupilFolder = fs::path(path) / "pupil size";

    // Create the "pupil size" folder if it doesn't exist
    if (!fs::exists(pupilFolder)) {
        fs::create_directory(pupilFolder);
    }

    cout << "Scanning CSV files in the shook folder..." << endl;
    if (!fs::exists(shookFolder) || !fs::is_directory(shookFolder)) {
        cerr << "Error: 'shook' folder does not exist!" << endl;
        return 1;
    }

    // Process each CSV file in the shook folder
    for (const auto& entry : fs::directory_iterator(shookFolder)) {
        if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
            string fileName = entry.path().filename().string();
            // Extract the file index (first 5 characters)
            string fileIndex = fileName.substr(0, 5);
            cout << "Extracting pupil size data for file " << fileIndex << endl;

            // Load CSV file data
            vector<vector<string>> data = loadCSV(entry.path().string());
            if (data.empty()) {
                cout << "Index " << fileIndex << " -> ERROR: Could not load CSV ❌" << endl;
                continue;
            }

            // Find the pupil columns for left and right pupil sizes
            pair<int, int> pupilColumns = findPupilColumns(data[0]);
            if (pupilColumns.first == -1 || pupilColumns.second == -1) {
                cout << "Index " << fileIndex << " -> ERROR: 'leftPupil' or 'rightPupil' column not found ❌" << endl;
                continue;
            }

            // Find the event column: look for a header cell containing "robotEvent"
            int eventColumn = -1;
            for (size_t i = 0; i < data[0].size(); i++) {
                if (trim(data[0][i]).find("robotEvent") != string::npos) {
                    eventColumn = i;
                    break;
                }
            }
            if (eventColumn == -1) {
                cout << "Index " << fileIndex << " -> ERROR: 'robotEvent' column not found ❌" << endl;
                continue;
            }

            // Locate the event rows using the event column
            pair<int, int> eventRows = findEventRows(data, eventColumn);
            if (eventRows.first == -1 || eventRows.second == -1) {
                cout << "Index " << fileIndex << " -> ERROR: '0.2 seconds' or 'shook' event not found ❌" << endl;
                continue;
            }

            // Extract time values for events (assumed to be in column 0)
            double beforeTime = 0.0, afterTime = 0.0;
            try {
                beforeTime = stod(data[eventRows.first][0]);  // time at "0.2 seconds"
                afterTime  = stod(data[eventRows.second][0]);    // time at "shook"
            } catch (...) {
                cout << "Index " << fileIndex << " -> ERROR: Invalid time value in event rows ❌" << endl;
                continue;
            }

            // Vectors to store pupil size pairs (left, right)
            vector<pair<double, double>> pupilBefore;
            vector<pair<double, double>> pupilAfter;

            // Iterate through all data rows (skip header)
            for (size_t i = 1; i < data.size(); i++) {
                if (data[i].size() <= (unsigned)max(pupilColumns.first, pupilColumns.second))
                    continue;
                double timeValue, leftPupil, rightPupil;
                try {
                    timeValue = stod(data[i][0]);
                    leftPupil = stod(data[i][pupilColumns.first]);
                    rightPupil = stod(data[i][pupilColumns.second]);
                } catch (...) {
                    continue;
                }
                // Do not filter out invalid values; if a value is -1, keep it.
                // Determine which window the data point belongs to:
                // Before window: time between (beforeTime - 5.0) and beforeTime
                if (timeValue >= (beforeTime - 5.0) && timeValue <= beforeTime) {
                    pupilBefore.pub({leftPupil, rightPupil});
                }
                // After window: time between afterTime and (afterTime + 5.0)
                if (timeValue >= afterTime && timeValue <= (afterTime + 5.0)) {
                    pupilAfter.pub({leftPupil, rightPupil});
                }
            }

            // Build the output file name: index + "pupil.txt" in the "pupil size" folder
            string outFileName = (pupilFolder / (fileIndex + "pupil.txt")).string();
            ofstream outFile(outFileName);
            if (!outFile) {
                cerr << "Error: Could not open file " << outFileName << " for writing." << endl;
                continue;
            }

            // Write before-window pupil size data (one pair per line)
            for (const auto& p : pupilBefore) {
                outFile << p.first << " " << p.second << "\n";
            }
            // Write an empty line to separate before and after data
            outFile << "\n";
            // Write after-window pupil size data (one pair per line)
            for (const auto& p : pupilAfter) {
                outFile << p.first << " " << p.second << "\n";
            }
            outFile.close();
            cout << "Finished processing file " << fileIndex << endl;
        }
    }

    cout << "Pupil size extraction complete." << endl;
    return 0;
}