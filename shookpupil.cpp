#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <limits>
#include <iomanip>
#include <cmath>  // For variance calculation
#include <algorithm>  // For trimming whitespace
#include <boost/math/distributions/students_t.hpp> 
#include <numeric>
#include <set>
using namespace std;
namespace fs = filesystem;
using namespace boost::math;
typedef long long ll;
typedef pair<ll,ll> pll;
#define pub push_back
#define mp make_pair
#define pob pop_back
#define X first
#define Y second
const ll INF = 0x3f3f3f3f3f3f3f3f;
//g++ shookpupil.cpp -I/opt/homebrew/include -L/opt/homebrew/lib -lboost_math_c99
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

// Function to find the column that contains "leftpupil" and "rightpupil"
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

// Function to find the row index of "0.2 seconds" and "shook"
pair<int, int> findEventRows(const vector<vector<string>>& data, int eventColumn) {
    int rowFor02 = -1, rowForShook = -1;
    for (size_t i = 1; i < data.size(); i++) { // Start from row 1 to skip header
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

double calculateStdDev(const vector<double>& values, double mean) {
    if (values.size() < 2) return -1.0;

    double variance = 0.0;
    for (double val : values) {
        variance += pow(val - mean, 2);
    }
    variance /= (values.size() - 1);
    
    return sqrt(variance);
}

// Function to compute pupil size averages before and after events
vector<double> calculatePupilAverages(const vector<vector<string>>& data, int timeCol, int leftPupilCol, int rightPupilCol, int rowFor02, int rowForShook) {
    double sumLeftBefore = 0.0, sumRightBefore = 0.0, leftcountBefore = 0, rightcountBefore = 0;
    double sumLeftAfter = 0.0, sumRightAfter = 0.0, leftcountAfter = 0, rightcountAfter = 0, beforecount=0, aftercount=0;
    double beforeTime = stod(data[rowFor02][timeCol]); //0.2 sec
    double timeAfter = stod(data[rowForShook][timeCol]); //shook
    double luminance, luminancecol=leftPupilCol-1, luminancebeforecnt=0, luminanceaftercnt=0, luminancebefore=0, luminanceafter=0;
    vector<double> leftbefore, rightbefore, leftafter, rightafter;
    for (size_t i = 1; i < data.size(); i++) { // Start from row 1 to skip header
        if (data[i].size() <= max(leftPupilCol, rightPupilCol)) continue;

        double timeValue, leftPupilSize, rightPupilSize;
        try {
            timeValue = stod(data[i][timeCol]);
            leftPupilSize = stod(data[i][leftPupilCol]);
            rightPupilSize = stod(data[i][rightPupilCol]);
            luminance=stod(data[i][luminancecol]);
        } catch (...) {
            continue;
        }

        if (timeValue >= (beforeTime - 5.0) && timeValue <= beforeTime) {
            if (leftPupilSize>0){
                sumLeftBefore += leftPupilSize;
                leftcountBefore++;
                leftbefore.pub(leftPupilSize);
            }
            if (rightPupilSize>0){
                sumRightBefore += rightPupilSize;
                rightcountBefore++;
                rightbefore.pub(rightPupilSize);
            }
            if (luminance>0){
                luminancebefore+=luminance;
                luminancebeforecnt++;
            }
            beforecount++;
        }

        if (timeValue >= timeAfter && timeValue <= (timeAfter + 5.0)) {
            if (leftPupilSize>0){
                sumLeftAfter += leftPupilSize;
                leftcountAfter++;
                leftafter.pub(leftPupilSize);
            }
            if (rightPupilSize>0){
                sumRightAfter += rightPupilSize;
                rightcountAfter++;
                rightafter.pub(rightPupilSize);
            }
            if (luminance>0){
                luminanceafter+=luminance;
                luminanceaftercnt++;
            }
            aftercount++;
        }
    }
    double avgLeftBefore = (leftcountBefore >= beforecount * 0.5) ? sumLeftBefore / leftcountBefore : -1;
    double avgRightBefore = (rightcountBefore >= beforecount * 0.5) ? sumRightBefore / rightcountBefore : -1;
    double avgLeftAfter = (leftcountAfter >= aftercount * 0.5) ? sumLeftAfter / leftcountAfter : -1;
    double avgRightAfter = (rightcountAfter >= aftercount * 0.5) ? sumRightAfter / rightcountAfter : -1;
    double avgluminancebefore=(luminancebeforecnt >= beforecount * 0.5) ? luminancebefore / luminancebeforecnt : -1;
    double avgluminanceafter=(luminanceaftercnt >= aftercount * 0.5) ? luminanceafter / luminanceaftercnt : -1;
    return{
        avgluminancebefore, 
        avgLeftBefore, static_cast<double>(leftbefore.size()), calculateStdDev(leftbefore, avgLeftBefore), avgRightBefore, static_cast<double>(rightbefore.size()), calculateStdDev(rightbefore, avgRightBefore),
        avgluminanceafter, 
        avgLeftAfter, static_cast<double>(leftafter.size()), calculateStdDev(leftafter, avgLeftAfter), avgRightAfter, static_cast<double>(rightafter.size()), calculateStdDev(rightbefore, avgRightBefore)
    };    
}
void saveVectorToFile(double index, double luminancebefore, double pupilbefore, double beforecnt, double beforesd, double luminanceafter, double pupilafter, double aftercnt, double aftersd, const string& filename) {
    ofstream outFile(filename, ios::app); // Open in append mode
    if (!outFile) {
        cerr << "Error: Could not open file " << filename << endl;
        return;
    }
    //n & sd is only for pupil size after, not before
    outFile<<index<<" "<<luminancebefore<<" "<<pupilbefore<<" "<<beforecnt<<" "<<beforesd<<" "<<luminanceafter<<" "<<pupilafter<<" "<<aftercnt<<" "<<aftersd<<'\n';
    outFile.close();
    cout << "Data saved to " << filename;
}

int main() {
    ios_base::sync_with_stdio(0);
    cin.tie(0);

    string path = ".";
    fs::path shookFolder = fs::path(path) / "shook";

    cout << fixed << setprecision(3);
    cout << "Scanning CSV files in the shook folder..." << endl;

    if (!fs::exists(shookFolder) || !fs::is_directory(shookFolder)) {
        cerr << "Error: 'shook' folder does not exist!" << endl;
        return 1;
    }

    cout << "\n==== Pupil Analysis Report ====\n";
    int validleftcnt=0, validrightcnt=0, totalcnt=0;
    double leftbefore=0, leftafter=0, rightbefore=0, rightafter=0;
    for (const auto& entry : fs::directory_iterator(shookFolder)) {
        if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
            totalcnt++;
        }
    }
    vector<double> leftpupil, rightpupil;
    int invalidluminancecnt=0;
    vector<string> invalidluminance;
    set<string> missingEventIndices;
    for (const auto& entry : fs::directory_iterator(shookFolder)) {
        if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
            string fileName = entry.path().filename().string();
            string fileIndex = fileName.substr(0, 5);
            // Load CSV file into 2D vector
            vector<vector<string>> data = loadCSV(entry.path().string());
            if (data.empty()) {
                cout << "Index " << fileIndex << " -> ERROR: Could not load CSV ❌" << endl;
                continue;
            }

            // Find column indices
            pair<int, int> pupilColumns = findPupilColumns(data[0]);
            if (pupilColumns.first == -1 || pupilColumns.second == -1) {
                cout << "Index " << fileIndex << " -> ERROR: 'leftpupil' or 'rightpupil' column not found ❌" << endl;
                continue;
            }

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

            // Find row indices
            pair<int, int> eventRows = findEventRows(data, eventColumn);
            if (eventRows.first == -1 || eventRows.second == -1) {
                cout << "Index " << fileIndex << " -> ERROR: '0.2 seconds' or 'shook' not found ❌" << endl;
                continue;
            }
            vector<double> datalist = calculatePupilAverages(data, 0, pupilColumns.first, pupilColumns.second, eventRows.first, eventRows.second);

//average luminance before [0], average left before [1], left before size [2], sd left before [3], average right before [4], right before size [5], sd right before [6]
//average luminance after [7], average left after [8], leftafter size [9], sd left after [10], average right after [11], rightafter size [12], sd right after [13]
            cout << "Index " << fileIndex << " -> ";
            if (datalist[0]>0||datalist[7]>0){ //average luminance check   
                if (datalist[1] < 0 || datalist[8] < 0) { //left eye before & after
                    cout << "invalid left eye ❌, ";
                } else {
                    cout << "Valid left eye ✅ ";
                    leftbefore += datalist[1];
                    leftafter += datalist[8];
                    validleftcnt++;
                    saveVectorToFile(stod(fileIndex), datalist[0], datalist[1], datalist[2], datalist[3], datalist[7], datalist[8], datalist[9], datalist[10], "leftpupil.txt");
                }
                if (datalist[4] < 0 || datalist[11] < 0) { //right eye before & after
                    cout << "invalid right eye ❌, " << '\n';
                } else {
                    cout << "Valid right eye ✅ " << '\n';
                    rightbefore += datalist[4];
                    rightafter += datalist[11];
                    validrightcnt++;
                    saveVectorToFile(stod(fileIndex), datalist[0], datalist[4], datalist[5], datalist[6], datalist[7], datalist[11], datalist[12], datalist[13], "rightpupil.txt");
                }
            }
            else{
                invalidluminancecnt++;
                invalidluminance.pub(fileIndex);
                cout<<"Invalid luminance";
            }
            cout<<'\n';
        }
    }

    cout << "\n==== Indices with Missing '0.2 seconds' Tag ====\n";
    for (const auto& index : missingEventIndices) {
        cout << index << " ";
    }
    cout << "\n\nValid left count: " << validleftcnt << " / " << totalcnt;
    cout << ", Valid right count: " << validrightcnt << " / " << totalcnt << '\n';
    cout << "Avg Left Before: " << leftbefore / validleftcnt << ", Avg Left After: " << leftafter / validleftcnt;
    cout << ", Avg Left Diff: " << (leftafter - leftbefore) / validleftcnt << '\n';
    cout << "Avg Right Before: " << rightbefore / validrightcnt << ", Avg Right After: " << rightafter / validrightcnt;
    cout << ", Avg Right Diff: " << (rightafter - rightbefore) / validrightcnt << '\n';
    cout << "Invalid luminance cnt "<<invalidluminancecnt<<" "<<invalidluminancecnt/totalcnt<<'\n';
    if (invalidluminance.size()){
        cout << "Invalid luminance: ";
        for (int i=0; i<invalidluminance.size(); ++i){
            cout<<invalidluminance[i]<<" ";
        }
        cout<<'\n';
    }
    else{
        cout<<"No Invalid Luminance"<<'\n';
    }
}