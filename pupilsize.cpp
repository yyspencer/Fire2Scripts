#include <iostream>
#include <fstream>
#include <string>
#include <limits>
using namespace std;
//considering each index's pupil size as one single data point
void processFile(const string& filename, const string& eyeLabel) {
    ifstream file(filename);
    if (!file.is_open()) {
        cerr << "Failed to open " << filename << endl;
        return;
    }

    string index;
    double lumBefore, pupilBefore, countBefore, stdBefore;
    double lumAfter, pupilAfter, countAfter, stdAfter;

    double sumBefore = 0, sumAfter = 0;
    int validCountBefore = 0, validCountAfter = 0;

    double minBefore = numeric_limits<double>::max();
    double maxBefore = numeric_limits<double>::lowest();
    double minAfter = numeric_limits<double>::max();
    double maxAfter = numeric_limits<double>::lowest();

    while (file >> index >> lumBefore >> pupilBefore >> countBefore >> stdBefore >> lumAfter >> pupilAfter >> countAfter >> stdAfter) {
        if (pupilBefore > 0) {
            sumBefore += pupilBefore;
            validCountBefore++;
            minBefore = min(minBefore, pupilBefore);
            maxBefore = max(maxBefore, pupilBefore);
        }
        if (pupilAfter > 0) {
            sumAfter += pupilAfter;
            validCountAfter++;
            minAfter = min(minAfter, pupilAfter);
            maxAfter = max(maxAfter, pupilAfter);
        }
    }

    file.close();

    cout << "== " << eyeLabel << " Eye ==" << endl;

    if (validCountBefore > 0) {
        cout << "Average Pupil Size Before: " << sumBefore / validCountBefore << endl;
        cout << "Min Pupil Size Before: " << minBefore << ", Max: " << maxBefore << endl;
    } else {
        cout << "No valid before data.\n";
    }

    if (validCountAfter > 0) {
        cout << "Average Pupil Size After: " << sumAfter / validCountAfter << endl;
        cout << "Min Pupil Size After: " << minAfter << ", Max: " << maxAfter << endl;
    } else {
        cout << "No valid after data.\n";
    }

    cout << endl;
}

int main() {
    processFile("leftpupil.txt", "Left");
    processFile("rightpupil.txt", "Right");
    return 0;
}