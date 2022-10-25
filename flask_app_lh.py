from flask import Flask, request
from flask_restful import Resource, Api
from samplelist import example_sample_list

app = Flask(__name__)
api = Api(app)

# master list of current sample lists
# key is the "ID". The sample list itself is JSON representing exactly what should be sent to the LH for a single sample list
sample_lists = {'1': example_sample_list}

# keeps track of which sample lists have been completed, in case requests come in for status updates on previous sample lists
completed_sample_lists = {}

class GetListofSampleLists(Resource):
    def get(self):
        return {'sampleLists': [sample_lists[id] for id in sample_lists.keys()]}, 200

class GetSampleList(Resource):
    def get(self, sample_list_id):
        return sample_lists[sample_list_id], 200

class PutSampleList(Resource):
    def post(self):
        data = request.get_json(force=True)
        new_id = max([int(k) for k in sample_lists.keys()]) + 1
        new_id = '%i' % new_id
        data['id'] = new_id
        sample_lists[new_id] = data
        return {new_id: sample_lists[new_id]}, 200

class PutSampleListValidation(Resource):
    def post(self, sample_list_id):
        data = request.get_json(force=True)
        # TODO: some stuff, parse 'validationType' for SUCCESS or ERROR
        return {sample_list_id, data}, 200

class PutSampleData(Resource):
    def post(self, sample_list_id):
        data = request.get_json(force=True)
        # TODO: some stuff
        # Probable logic: once sample data is posted as successful, flag it as completed and move from sample_lists to completed_sample_lists
        return {sample_list_id, data}, 200

api.add_resource(GetListofSampleLists, '/LH/GetNewSampleLists')
api.add_resource(GetSampleList, '/LH/GetSampleList/<sample_list_id>')
api.add_resource(PutSampleList, '/LH/PutSampleList/')
api.add_resource(PutSampleData, '/LH/PutSampleData/')
api.add_resource(PutSampleListValidation, '/LH/PutSampleListValidation/<sample_list_id>')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)